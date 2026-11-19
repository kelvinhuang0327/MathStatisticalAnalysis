"""Build the read-only, cross-source Replay strategy identity index."""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import cast

from lottolab.application.historical_replay_adapters import (
    BigLottoReplayAdapter,
    Daily539ReplayAdapter,
    PowerLottoReplayAdapter,
    ReplayStrategyBinding,
    ReplayStrategyImplementation,
    binding_from_implementation,
    binding_from_p638_spec,
    t539_replay_bindings,
)
from lottolab.application.native_replay_inventory import native_strategy_inventory
from lottolab.application.use_cases.generate_bet import (
    instantiate_adapter,
    instantiate_portfolio_adapter,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    FullStrategyCatalog,
    ReproductionStatus,
    load_full_strategy_catalog,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayBehavior
from lottolab.domain.replay_strategy_inventory import (
    ReplayDataStatus,
    ReplayExecutionCapability,
    ReplayLifecycleStatus,
    ReplayStrategyAdapterMapping,
    ReplayStrategyBindingEvidence,
    ReplayStrategyIdentityMapping,
    ReplayStrategyInventory,
    ReplayStrategyInventoryItem,
    ReplayStrategySourceCount,
)
from lottolab.domain.strategies import ResponseShape, StrategyDescriptor
from lottolab.strategies.adapters.powerlotto_wave1 import WAVE1_STRATEGIES
from lottolab.strategies.adapters.powerlotto_wave2 import WAVE2_STRATEGIES
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

_PRODUCTION_CATALOG_LOCATOR = "src/lottolab/strategies/catalog.py"
_FULL_CATALOG_LOCATOR = "src/lottolab/strategies/data/biglotto_full_strategy_catalog_v1.json"
_FULL_CATALOG_EVIDENCE_LOCATOR = "src/lottolab/strategies/data"
_REPLAY_BATCH_LOCATOR = "src/lottolab/strategies/data/biglotto_replay_batch_exact2_evidence_v1.json"
_EXACT_NATIVE_LOCATOR = (
    "src/lottolab/strategies/data/biglotto_exact_native_k5_115000084_records_v1.json"
)
_LEGACY_SNAPSHOT_LOCATOR = "tests/fixtures/legacy/p600b/strategy_catalog.json"
_ADAPTER_ROOT = Path(__file__).resolve().parents[1] / "strategies" / "adapters"
_DATA_ROOT = Path(__file__).resolve().parents[1] / "strategies" / "data"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@dataclass(slots=True)
class _MutableItem:
    lottery_type: LotteryType
    strategy_id: str
    display_name: str
    strategy_version: str | None
    source_kind: str
    source_locator: str
    lifecycle_status: ReplayLifecycleStatus
    replay_data_status: ReplayDataStatus
    execution_capability: ReplayExecutionCapability
    reconstruction_reason: str
    historical_data_count: int = 0
    historical_execution_count: int = 0
    source_statuses: set[str] = field(default_factory=lambda: set())
    sources: dict[
        tuple[str, str, str, str | None, str, str | None], ReplayStrategyIdentityMapping
    ] = field(
        default_factory=lambda: cast(
            dict[
                tuple[str, str, str, str | None, str, str | None],
                ReplayStrategyIdentityMapping,
            ],
            {},
        )
    )
    adapter_mapping: ReplayStrategyAdapterMapping | None = None
    reconstructable: bool | None = None
    wrapper_callable: bool | None = None
    backfill_native_binding: bool | None = None
    execution_block_reason: str | None = None
    backfill_native_binding_sources: tuple[ReplayStrategyBindingEvidence, ...] = ()

    @property
    def identity(self) -> tuple[LotteryType, str, str | None]:
        return (self.lottery_type, self.strategy_id, self.strategy_version)

    def add_source(self, source: ReplayStrategyIdentityMapping) -> None:
        key = (
            source.source_kind,
            source.source_locator,
            source.strategy_id,
            source.strategy_version,
            source.mapping_kind,
            source.source_status,
        )
        self.sources[key] = source
        if source.source_status is not None:
            self.source_statuses.add(source.source_status)

    def freeze(self) -> ReplayStrategyInventoryItem:
        sources = tuple(self.sources[key] for key in sorted(self.sources))
        return ReplayStrategyInventoryItem(
            lottery_type=self.lottery_type,
            strategy_id=self.strategy_id,
            display_name=self.display_name,
            strategy_version=self.strategy_version,
            source_kind=self.source_kind,
            source_locator=self.source_locator,
            lifecycle_status=self.lifecycle_status,
            replay_data_status=self.replay_data_status,
            execution_capability=self.execution_capability,
            reconstruction_reason=self.reconstruction_reason,
            historical_data_count=self.historical_data_count,
            alias_or_identity_mapping=sources,
            adapter_mapping=self.adapter_mapping,
            source_statuses=tuple(sorted(self.source_statuses)),
            historical_execution_count=self.historical_execution_count,
            reconstructable=self.reconstructable,
            wrapper_callable=self.wrapper_callable,
            backfill_native_binding=self.backfill_native_binding,
            execution_block_reason=self.execution_block_reason,
            backfill_native_binding_sources=self.backfill_native_binding_sources,
        )


@dataclass(frozen=True, slots=True)
class _CodeIdentity:
    source_path: str
    class_name: str
    strategy_id: str
    strategy_name: str
    strategy_version: str
    supported_lottery_types: tuple[LotteryType, ...]
    source_status: str | None


_POWER_GRAPH_CODE_IDENTITY = _CodeIdentity(
    source_path="src/lottolab/strategies/adapters/powerlotto_graph_synergy.py",
    class_name="PowerLottoGraphSynergySeed42Adapter",
    strategy_id="power_graph_synergy_seed42_2bet",
    strategy_name="威力彩 Graph Synergy Louvain (固定種子42)",
    strategy_version="v0.1-seed42",
    supported_lottery_types=(LotteryType.POWER_LOTTO,),
    source_status="CODE_PRESENT",
)
_DIRECT_CODE_BINDING_IDENTITIES = frozenset(
    {
        (LotteryType.BIG_LOTTO, "research_biglotto__quick_ml_corrected_successor_v1", "v1"),
        (
            LotteryType.BIG_LOTTO,
            "research_biglotto__k3_nonoverlap_optimizer_candidate_20261116",
            "v1.0.0",
        ),
        (
            LotteryType.BIG_LOTTO,
            "research_biglotto__k3_nonoverlap_ecp_candidate_20261116",
            "v1.0.0",
        ),
    }
)


@dataclass(frozen=True, slots=True)
class _HistoricalEvidence:
    execution_count: int
    locator: str


def _source_mapping(
    *,
    kind: str,
    locator: str,
    strategy_id: str,
    version: str | None,
    mapping: str,
    status: str | None = None,
) -> ReplayStrategyIdentityMapping:
    return ReplayStrategyIdentityMapping(
        source_kind=kind,
        source_locator=locator,
        strategy_id=strategy_id,
        strategy_version=version,
        mapping_kind=mapping,
        source_status=status,
    )


def _identity_key(
    lottery_type: LotteryType, strategy_id: str, version: str | None
) -> tuple[LotteryType, str, str | None]:
    return (lottery_type, strategy_id, version)


def _add_item(
    items: dict[tuple[LotteryType, str, str | None], _MutableItem],
    *,
    lottery_type: LotteryType,
    strategy_id: str,
    display_name: str,
    strategy_version: str | None,
    source_kind: str,
    source_locator: str,
    lifecycle_status: ReplayLifecycleStatus,
    replay_data_status: ReplayDataStatus,
    execution_capability: ReplayExecutionCapability,
    reconstruction_reason: str,
    source: ReplayStrategyIdentityMapping,
    adapter_mapping: ReplayStrategyAdapterMapping | None = None,
    source_statuses: tuple[str, ...] = (),
) -> _MutableItem:
    key = _identity_key(lottery_type, strategy_id, strategy_version)
    item = items.get(key)
    if item is None:
        item = _MutableItem(
            lottery_type=lottery_type,
            strategy_id=strategy_id,
            display_name=display_name,
            strategy_version=strategy_version,
            source_kind=source_kind,
            source_locator=source_locator,
            lifecycle_status=lifecycle_status,
            replay_data_status=replay_data_status,
            execution_capability=execution_capability,
            reconstruction_reason=reconstruction_reason,
            adapter_mapping=adapter_mapping,
        )
        items[key] = item
    elif item.display_name == item.strategy_id and display_name != strategy_id:
        item.display_name = display_name
    if adapter_mapping is not None:
        if item.adapter_mapping is None:
            item.adapter_mapping = adapter_mapping
            item.execution_capability = ReplayExecutionCapability.EXECUTABLE
        elif item.adapter_mapping.strategy_id != strategy_id or (
            item.adapter_mapping.strategy_version != strategy_version
        ):
            raise ValueError("adapter identity conflicts with the canonical strategy version")
    item.add_source(source)
    item.source_statuses.update(source_statuses)
    return item


def _descriptor_fingerprint(descriptor: StrategyDescriptor) -> str:
    payload = {
        "provenance": descriptor.provenance,
        "strategy_id": descriptor.strategy_id,
        "version": descriptor.version,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()


def _production_binding(
    descriptor: StrategyDescriptor,
    registry: ExecutableRegistry,
    lottery_type: LotteryType,
) -> tuple[ReplayStrategyBinding | None, str | None]:
    """Resolve and type-check the catalog adapter through a Replay wrapper."""

    try:
        if lottery_type not in descriptor.lottery_types:
            raise ValueError(f"strategy does not support {lottery_type.value}")
        if not descriptor.executable:
            raise ValueError("catalog marks strategy as not executable")
        if lottery_type is LotteryType.POWER_LOTTO and descriptor.strategy_id not in {
            spec.strategy_id for spec in (*WAVE1_STRATEGIES, *WAVE2_STRATEGIES)
        }:
            raise ValueError("no complete native second-zone replay source")
        adapter_class = registry.load_adapter(descriptor.strategy_id)
        implementation = (
            instantiate_adapter(descriptor.strategy_id, adapter_class)
            if descriptor.response_shape is ResponseShape.SINGLE_TICKET
            else instantiate_portfolio_adapter(descriptor.strategy_id, adapter_class)
        )
        actual_identity = (
            getattr(implementation, "strategy_id", None),
            getattr(implementation, "strategy_name", None),
            getattr(implementation, "strategy_version", None),
        )
        expected_identity = (
            descriptor.strategy_id,
            descriptor.strategy_name,
            descriptor.version,
        )
        if actual_identity != expected_identity:
            raise ValueError(f"adapter identity mismatch: expected {expected_identity!r}")
        supported_methods = (
            (
                "get_replay_tickets",
                "get_bets_with_emission",
                "get_bets",
                "get_one_bet_with_emission",
                "get_one_bet",
            )
            if lottery_type is not LotteryType.POWER_LOTTO
            else ("get_bets_with_emission", "get_one_bet_with_emission", "get_one_bet")
        )
        if not any(callable(getattr(implementation, name, None)) for name in supported_methods):
            raise TypeError("adapter has no ticket method accepted by its Replay adapter")
        unseeded_live_rng = any(
            item == "randomness:PROCESS_GLOBAL_UNSEEDED_MATH_RANDOM_EQUIVALENT"
            for item in descriptor.provenance
        )
        binding = binding_from_implementation(
            cast(ReplayStrategyImplementation, implementation),
            behavior=(
                ReplayBehavior.LEGACY_NONDETERMINISTIC
                if unseeded_live_rng
                else ReplayBehavior.DETERMINISTIC
            ),
            fingerprint=_descriptor_fingerprint(descriptor),
        )
        if lottery_type is LotteryType.BIG_LOTTO:
            BigLottoReplayAdapter((binding,))
        elif lottery_type is LotteryType.DAILY_539:
            Daily539ReplayAdapter((binding,))
        elif lottery_type is LotteryType.POWER_LOTTO:
            PowerLottoReplayAdapter((binding,))
        else:  # pragma: no cover - LotteryType is a closed project enum.
            raise ValueError(f"unsupported lottery type {lottery_type.value}")
        # The engine binding is intentionally constructed with the version in
        # the production descriptor, never from lifecycle alone.
        if binding.strategy.strategy_version != descriptor.version:
            raise ValueError("Replay binding version does not match the catalog descriptor")
        return binding, None
    except Exception as exc:  # Keep the identity visible with an exact blocker.
        detail = str(exc).replace("\n", " ").strip() or "no detail"
        return None, f"{type(exc).__name__}: {detail[:240]}"


def _binding_mapping(
    binding: ReplayStrategyBinding, adapter_type: type[object], locator: str
) -> ReplayStrategyAdapterMapping:
    return ReplayStrategyAdapterMapping(
        replay_adapter=f"{adapter_type.__module__}.{adapter_type.__qualname__}",
        implementation_locator=locator,
        strategy_id=binding.strategy.strategy_id,
        strategy_version=binding.strategy.strategy_version,
    )


def _literal_string(class_node: ast.ClassDef, field_name: str) -> str | None:
    for statement in class_node.body:
        if isinstance(statement, ast.Assign):
            targets = statement.targets
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
            value = statement.value
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == field_name for target in targets) and (
            isinstance(value, ast.Constant) and isinstance(value.value, str)
        ):
            return value.value
    return None


def _literal_lottery_types(class_node: ast.ClassDef) -> tuple[LotteryType, ...]:
    expression: ast.expr | None = None
    for statement in class_node.body:
        if isinstance(statement, ast.Assign):
            targets = statement.targets
            value = statement.value
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
            value = statement.value
        else:
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "supported_lottery_types"
            for target in targets
        ):
            expression = value
            break
    if not isinstance(expression, (ast.Tuple, ast.List)):
        return ()
    types: list[LotteryType] = []
    for element in expression.elts:
        if (
            isinstance(element, ast.Attribute)
            and isinstance(element.value, ast.Name)
            and element.value.id == "LotteryType"
        ):
            try:
                types.append(LotteryType(element.attr))
            except ValueError:
                continue
    return tuple(dict.fromkeys(types))


def _scan_adapter_code() -> tuple[tuple[_CodeIdentity, ...], int]:
    """Find code identities without importing or executing source modules."""

    identities: list[_CodeIdentity] = []
    class_row_count = 0
    for source_path in sorted(_ADAPTER_ROOT.rglob("*.py")):
        try:
            module = ast.parse(source_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(module):
            if not isinstance(node, ast.ClassDef):
                continue
            strategy_id = _literal_string(node, "strategy_id")
            strategy_version = _literal_string(node, "strategy_version")
            if strategy_id is None or strategy_version is None:
                continue
            class_row_count += 1
            strategy_name = _literal_string(node, "strategy_name") or strategy_id
            source_status = _literal_string(node, "status")
            relative_path = source_path.relative_to(_REPOSITORY_ROOT).as_posix()
            identity = _CodeIdentity(
                source_path=relative_path,
                class_name=node.name,
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                strategy_version=strategy_version,
                supported_lottery_types=_literal_lottery_types(node),
                source_status=source_status,
            )
            identities.append(identity)
    return tuple(
        sorted(
            identities,
            key=lambda item: (
                item.strategy_id,
                item.strategy_version,
                item.source_path,
                item.class_name,
            ),
        )
    ), class_row_count


def _successful_count(value: object) -> int | None:
    record = _as_json_object(value)
    if record is None:
        return None
    for key in ("successful_execution_count", "ok_execution_count"):
        count = record.get(key)
        if type(count) is int and count >= 0:
            return count
    for key in ("execution_status_counts", "replay_status_counts", "status_counts"):
        counts = _as_json_object(record.get(key))
        if counts is not None:
            successful = [
                count
                for status, count in counts.items()
                if status in {"OK", "COMPLETE", "SUCCESS", "SUCCESSFUL"}
                and type(count) is int
                and count >= 0
            ]
            if successful:
                return sum(successful)
    return None


def _walk_method_evidence(
    value: object,
    *,
    locator: str,
    counts: dict[str, _HistoricalEvidence],
) -> None:
    record = _as_json_object(value)
    if record is not None:
        method_id = record.get("legacy_method_id")
        execution_count = _successful_count(record)
        if isinstance(method_id, str) and execution_count is not None:
            current = counts.get(method_id)
            if current is None or execution_count > current.execution_count:
                counts[method_id] = _HistoricalEvidence(
                    execution_count,
                    f"{locator}#legacy_method_id={method_id}",
                )
        for child in record.values():
            _walk_method_evidence(child, locator=locator, counts=counts)
    elif isinstance(value, list):
        for child in cast(list[object], value):
            _walk_method_evidence(child, locator=locator, counts=counts)


def _as_json_object(value: object) -> dict[str, object] | None:
    """Narrow parsed JSON mappings to string-keyed objects at each boundary."""

    if not isinstance(value, dict):
        return None
    keys = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in keys):
        return None
    return cast(dict[str, object], value)


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _historical_evidence(
    full_catalog: FullStrategyCatalog,
) -> tuple[
    dict[str, _HistoricalEvidence],
    dict[tuple[str, str], _HistoricalEvidence],
    dict[tuple[str, str], _HistoricalEvidence],
    int,
    int,
    tuple[str, ...],
    dict[str, object] | None,
]:
    method_counts: dict[str, _HistoricalEvidence] = {}
    exact_batch_counts: dict[tuple[str, str], _HistoricalEvidence] = {}
    exact_native_counts: dict[tuple[str, str], _HistoricalEvidence] = {}
    loaded_artifacts = 0
    missing_artifacts = 0
    integrity_issues: list[str] = []
    for filename, expected_sha256, role in full_catalog.source_artifacts:
        artifact_path = _DATA_ROOT / filename
        if not artifact_path.is_file():
            missing_artifacts += 1
            integrity_issues.append(f"MISSING_MANIFEST_ARTIFACT:{filename}")
            continue
        payload_bytes = artifact_path.read_bytes()
        actual_sha256 = hashlib.sha256(payload_bytes).hexdigest()
        # Some catalog entries pin the canonical evidence content hash rather
        # than the physical JSON file hash. Verify both the declared value and
        # the canonical content; a copied embedded digest alone proves nothing.
        if actual_sha256 != expected_sha256:
            try:
                evidence = _as_json_object(
                    json.loads(payload_bytes, object_pairs_hook=_unique_json_object)
                )
            except (UnicodeDecodeError, ValueError):
                evidence = None
            if evidence is not None and evidence.get("evidence_sha256") == expected_sha256:
                canonical = json.dumps(
                    {key: value for key, value in evidence.items() if key != "evidence_sha256"},
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
                actual_sha256 = hashlib.sha256(canonical).hexdigest()
        if actual_sha256 != expected_sha256:
            integrity_issues.append(f"SHA256_MISMATCH:{filename}")
            continue
        loaded_artifacts += 1
        if "CAUSAL_BACKTEST" not in role and "CAUSAL_BACKTEST" not in filename.upper():
            continue
        payload = json.loads(payload_bytes)
        _walk_method_evidence(
            payload,
            locator=f"{_FULL_CATALOG_EVIDENCE_LOCATOR}/{filename}",
            counts=method_counts,
        )
        if filename == Path(_REPLAY_BATCH_LOCATOR).name:
            rows = payload.get("strategies", ())
            if not isinstance(rows, list):
                continue
            for row_value in cast(list[object], rows):
                row = _as_json_object(row_value)
                if row is None:
                    continue
                strategy_id = row.get("catalog_strategy_id")
                strategy_version = row.get("strategy_version")
                execution_count = row.get("execution_count")
                if (
                    isinstance(strategy_id, str)
                    and isinstance(strategy_version, str)
                    and type(execution_count) is int
                ):
                    identity = (strategy_id, strategy_version)
                    current = exact_batch_counts.get(identity)
                    if current is None or execution_count > current.execution_count:
                        exact_batch_counts[identity] = _HistoricalEvidence(
                            execution_count,
                            f"{_REPLAY_BATCH_LOCATOR}#strategies[{strategy_id}]",
                        )

    exact_native_payload: dict[str, object] | None = None
    exact_native_path = _DATA_ROOT / Path(_EXACT_NATIVE_LOCATOR).name
    if exact_native_path.is_file():
        raw = exact_native_path.read_bytes()
        try:
            payload_value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload_value = None
        payload_object = _as_json_object(payload_value)
        if payload_object is None:
            integrity_issues.append(f"INVALID_JSON:{_EXACT_NATIVE_LOCATOR}")
        else:
            projection_sha256 = payload_object.get("projection_sha256")
            canonical = json.dumps(
                {key: value for key, value in payload_object.items() if key != "projection_sha256"},
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            if (
                not isinstance(projection_sha256, str)
                or hashlib.sha256(canonical).hexdigest() != projection_sha256
            ):
                integrity_issues.append(f"PROJECTION_SHA256_MISMATCH:{_EXACT_NATIVE_LOCATOR}")
            else:
                exact_native_payload = payload_object
        payload = exact_native_payload or {}
        rows = payload.get("records", ())
        grouped: dict[tuple[str, str], _HistoricalEvidence] = {}
        native_rows = cast(list[object], rows) if isinstance(rows, list) else []
        for row_value in native_rows:
            row = _as_json_object(row_value)
            if row is None:
                continue
            strategy_id = row.get("strategy_id")
            version = row.get("catalog_strategy_version") or row.get("strategy_version")
            status_counts = _as_json_object(row.get("replay_status_counts"))
            complete = status_counts.get("COMPLETE") if status_counts is not None else None
            if not isinstance(strategy_id, str) or type(complete) is not int or complete < 0:
                continue
            # The catalog version is the exact source identity when present;
            # rows with a null catalog version remain their own artifact version.
            key = (strategy_id, version if isinstance(version, str) else "")
            current = grouped.get(key)
            if current is None or complete > current.execution_count:
                grouped[key] = _HistoricalEvidence(
                    complete,
                    (
                        f"{_EXACT_NATIVE_LOCATOR}#strategy_id={strategy_id}"
                        f"&version={version or 'UNKNOWN'}"
                    ),
                )
        for key, evidence in grouped.items():
            current = exact_native_counts.get(key)
            if current is None or evidence.execution_count > current.execution_count:
                exact_native_counts[key] = evidence
    else:
        integrity_issues.append(f"MISSING_PACKAGED_ARTIFACT:{_EXACT_NATIVE_LOCATOR}")
    return (
        method_counts,
        exact_batch_counts,
        exact_native_counts,
        loaded_artifacts,
        missing_artifacts,
        tuple(integrity_issues),
        exact_native_payload,
    )


def _catalog_lineage(descriptor: StrategyDescriptor) -> tuple[str, ...]:
    return tuple(
        value.split(":", 1)[1]
        for value in descriptor.provenance
        if value.startswith("full_strategy_catalog_id:")
    )


def _load_legacy_snapshot() -> tuple[dict[tuple[str, str], str], int]:
    snapshot_path = _REPOSITORY_ROOT / _LEGACY_SNAPSHOT_LOCATOR
    if not snapshot_path.is_file():
        return {}, 0
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return {}, 0
    result: dict[tuple[str, str], str] = {}
    snapshot_rows = cast(list[object], payload)
    for row_value in snapshot_rows:
        row = _as_json_object(row_value)
        if row is None:
            continue
        strategy_id = row.get("strategy_id")
        version = row.get("version")
        lifecycle = row.get("lifecycle_status")
        if isinstance(strategy_id, str) and isinstance(version, str) and isinstance(lifecycle, str):
            result[(strategy_id, version)] = lifecycle
    return result, len(snapshot_rows)


def _adapter_for_lottery(lottery_type: LotteryType) -> type[object]:
    if lottery_type is LotteryType.BIG_LOTTO:
        return BigLottoReplayAdapter
    if lottery_type is LotteryType.DAILY_539:
        return Daily539ReplayAdapter
    if lottery_type is LotteryType.POWER_LOTTO:
        return PowerLottoReplayAdapter
    raise ValueError(f"unsupported lottery type {lottery_type.value}")


def _primary_adapter_mapping(
    binding: ReplayStrategyBinding,
    lottery_type: LotteryType,
    implementation_locator: str,
) -> ReplayStrategyAdapterMapping:
    return _binding_mapping(binding, _adapter_for_lottery(lottery_type), implementation_locator)


def _add_production_items(
    items: dict[tuple[LotteryType, str, str | None], _MutableItem],
    descriptors: tuple[StrategyDescriptor, ...],
    registry: ExecutableRegistry,
    legacy_statuses: dict[tuple[str, str], str],
) -> dict[str, tuple[LotteryType, str]]:
    lineages: dict[str, tuple[LotteryType, str]] = {}
    for descriptor in descriptors:
        source_status = descriptor.lifecycle_status.value
        locator = f"{_PRODUCTION_CATALOG_LOCATOR}#strategy_id={descriptor.strategy_id}"
        for lottery_type in descriptor.lottery_types:
            binding, blocker = _production_binding(descriptor, registry, lottery_type)
            if binding is None:
                capability = ReplayExecutionCapability.UNAVAILABLE
                data_status = ReplayDataStatus.NO_HISTORY
                adapter_mapping = None
                reason = f"Production adapter did not resolve to a Replay binding: {blocker}"
            else:
                capability = ReplayExecutionCapability.EXECUTABLE
                data_status = ReplayDataStatus.REBUILDABLE
                adapter_mapping = _primary_adapter_mapping(
                    binding,
                    lottery_type,
                    descriptor.adapter_path or "missing adapter_path",
                )
                reason = (
                    "The catalog adapter resolved to an identity-matched ReplayStrategyBinding; "
                    "no retained per-draw prediction rows were found in the packaged sources."
                )
            item = _add_item(
                items,
                lottery_type=lottery_type,
                strategy_id=descriptor.strategy_id,
                display_name=descriptor.strategy_name,
                strategy_version=descriptor.version,
                source_kind="PRODUCTION_CATALOG",
                source_locator=locator,
                lifecycle_status=ReplayLifecycleStatus(source_status),
                replay_data_status=data_status,
                execution_capability=capability,
                reconstruction_reason=reason,
                source=_source_mapping(
                    kind="PRODUCTION_CATALOG",
                    locator=locator,
                    strategy_id=descriptor.strategy_id,
                    version=descriptor.version,
                    mapping="CANONICAL_PRODUCTION_IDENTITY",
                    status=source_status,
                ),
                adapter_mapping=adapter_mapping,
                source_statuses=(source_status,),
            )
            prior_lifecycle = legacy_statuses.get((descriptor.strategy_id, descriptor.version))
            if prior_lifecycle is not None:
                item.add_source(
                    _source_mapping(
                        kind="LEGACY_CATALOG_SNAPSHOT",
                        locator=f"{_LEGACY_SNAPSHOT_LOCATOR}#strategy_id={descriptor.strategy_id}",
                        strategy_id=descriptor.strategy_id,
                        version=descriptor.version,
                        mapping="EXACT_ID_AND_VERSION_SNAPSHOT",
                        status=prior_lifecycle,
                    )
                )

        for full_id in _catalog_lineage(descriptor):
            if len(descriptor.lottery_types) == 1:
                lineages[full_id] = (descriptor.lottery_types[0], descriptor.version)
    return lineages


def _add_full_catalog_items(
    items: dict[tuple[LotteryType, str, str | None], _MutableItem],
    full_catalog: FullStrategyCatalog,
    method_evidence: dict[str, _HistoricalEvidence],
    exact_batch_evidence: dict[tuple[str, str], _HistoricalEvidence],
    exact_native_evidence: dict[tuple[str, str], _HistoricalEvidence],
    production_lineages: dict[str, tuple[LotteryType, str]],
) -> None:
    for record in full_catalog.records:
        identity = (record.strategy_id, record.strategy_version)
        evidence = (
            method_evidence.get(record.legacy_method_id)
            or exact_batch_evidence.get(identity)
            or exact_native_evidence.get(identity)
        )
        historical_execution_count = 0 if evidence is None else evidence.execution_count
        if record.reproduction_status is ReproductionStatus.CLOSED_UNEXECUTABLE:
            lifecycle_status = ReplayLifecycleStatus.REJECTED
            data_status = ReplayDataStatus.REJECTED
            reason = f"CLOSED_UNEXECUTABLE: {record.status_reason}"
        elif record.reproduction_status is ReproductionStatus.DUPLICATE_ALIAS:
            lifecycle_status = ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED
            data_status = ReplayDataStatus.NO_HISTORY
            reason = (
                f"DUPLICATE_ALIAS targets {record.duplicate_alias_target}; "
                "the alias identity is retained and is not an independent executable strategy."
            )
        elif evidence is not None:
            lifecycle_status = ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED
            data_status = ReplayDataStatus.ARTIFACT_ONLY
            reason = (
                f"{record.reproduction_status.value}: checksum-pinned source evidence records "
                f"{historical_execution_count} completed historical executions, but the packaged "
                "source contains no retained per-draw prediction rows or exact-version Replay "
                "adapter."
            )
        else:
            lifecycle_status = ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED
            data_status = ReplayDataStatus.NO_HISTORY
            reason = (
                f"{record.reproduction_status.value}: no per-draw Replay data or current "
                "exact-version "
                "Replay adapter was found for this research identity."
            )
        locator = f"{_FULL_CATALOG_LOCATOR}#strategy_id={record.strategy_id}"
        source_statuses = (
            record.reproduction_status.value,
            record.legacy_runnable_status,
            record.legacy_recommended_action,
            record.r2_safety_disposition,
        )
        item = _add_item(
            items,
            lottery_type=LotteryType.BIG_LOTTO,
            strategy_id=record.strategy_id,
            display_name=record.legacy_method_id,
            strategy_version=record.strategy_version,
            source_kind="B649_RESEARCH_CATALOG",
            source_locator=locator,
            lifecycle_status=lifecycle_status,
            replay_data_status=data_status,
            execution_capability=ReplayExecutionCapability.UNAVAILABLE,
            reconstruction_reason=reason,
            source=_source_mapping(
                kind="B649_RESEARCH_CATALOG",
                locator=locator,
                strategy_id=record.strategy_id,
                version=record.strategy_version,
                mapping=(
                    f"DUPLICATE_ALIAS_TARGET:{record.duplicate_alias_target}"
                    if record.duplicate_alias_target is not None
                    else "CANONICAL_RESEARCH_IDENTITY"
                ),
                status=record.reproduction_status.value,
            ),
            source_statuses=source_statuses,
        )
        item.add_source(
            _source_mapping(
                kind="B649_RESEARCH_SOURCE_CODE",
                locator=(f"{record.source_path}@{record.source_commit}#{record.source_blob_id}"),
                strategy_id=record.strategy_id,
                version=record.strategy_version,
                mapping=f"SOURCE_SHA256:{record.source_sha256}",
                status=record.source_scan_status,
            )
        )
        item.historical_execution_count = max(
            item.historical_execution_count, historical_execution_count
        )
        if evidence is not None:
            item.add_source(
                _source_mapping(
                    kind="B649_REPLAY_ARTIFACT_SUMMARY",
                    locator=evidence.locator,
                    strategy_id=record.strategy_id,
                    version=record.strategy_version,
                    mapping="EXACT_LEGACY_METHOD_ID_AND_VERSION",
                    status=record.reproduction_status.value,
                )
            )
        lineage = production_lineages.get(record.strategy_id)
        if lineage is not None and lineage[1] != record.strategy_version:
            production_locator = f"{_PRODUCTION_CATALOG_LOCATOR}#strategy_id={record.strategy_id}"
            item.add_source(
                _source_mapping(
                    kind="PRODUCTION_CATALOG",
                    locator=production_locator,
                    strategy_id=record.strategy_id,
                    version=lineage[1],
                    mapping="SAME_ID_DIFFERENT_VERSION_RETAINED_SEPARATELY",
                    status=ReplayLifecycleStatus.ONLINE.value,
                )
            )


def _add_replay_binding_item(
    items: dict[tuple[LotteryType, str, str | None], _MutableItem],
    *,
    lottery_type: LotteryType,
    binding: ReplayStrategyBinding,
    source_kind: str,
    source_locator: str,
    implementation_locator: str,
) -> None:
    strategy = binding.strategy
    adapter_mapping = _primary_adapter_mapping(binding, lottery_type, implementation_locator)
    locator = f"{source_locator}#strategy_id={strategy.strategy_id}"
    _add_item(
        items,
        lottery_type=lottery_type,
        strategy_id=strategy.strategy_id,
        display_name=strategy.strategy_name,
        strategy_version=strategy.strategy_version,
        source_kind=source_kind,
        source_locator=locator,
        lifecycle_status=ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED,
        replay_data_status=ReplayDataStatus.RECONSTRUCTABLE,
        execution_capability=ReplayExecutionCapability.EXECUTABLE,
        reconstruction_reason=(
            "An existing target-native Replay adapter accepted this exact id/version binding; "
            "the source identity is not promoted into the production catalog."
        ),
        source=_source_mapping(
            kind=source_kind,
            locator=locator,
            strategy_id=strategy.strategy_id,
            version=strategy.strategy_version,
            mapping="EXACT_REPLAY_ADAPTER_BINDING",
            status="UNREGISTERED_REPLAY_ADAPTER",
        ),
        adapter_mapping=adapter_mapping,
        source_statuses=("UNREGISTERED_REPLAY_ADAPTER",),
    )


def _code_identity_lottery(
    identity: _CodeIdentity,
    items: dict[tuple[LotteryType, str, str | None], _MutableItem],
) -> LotteryType | None:
    candidates = {
        key[0]
        for key in items
        if key[1] == identity.strategy_id and key[2] == identity.strategy_version
    }
    if len(candidates) == 1:
        return next(iter(candidates))
    if identity.supported_lottery_types:
        if len(identity.supported_lottery_types) == 1:
            return identity.supported_lottery_types[0]
        return None
    return None


def _direct_code_binding(
    identity: _CodeIdentity,
) -> tuple[ReplayStrategyBinding | None, str | None]:
    module_path = identity.source_path.removeprefix("src/").removesuffix(".py").replace("/", ".")
    try:
        module = importlib.import_module(module_path)
        adapter_class = getattr(module, identity.class_name)
        implementation = adapter_class()
        if not any(
            callable(getattr(implementation, name, None))
            for name in (
                "get_replay_tickets",
                "get_bets_with_emission",
                "get_bets",
                "get_one_bet_with_emission",
                "get_one_bet",
            )
        ):
            raise TypeError("source class has no supported ticket method")
        binding = binding_from_implementation(
            cast(ReplayStrategyImplementation, implementation),
            behavior=ReplayBehavior.DETERMINISTIC,
        )
        if (
            binding.strategy.strategy_id != identity.strategy_id
            or binding.strategy.strategy_version != identity.strategy_version
        ):
            raise ValueError("direct source binding id/version mismatch")
        if len(identity.supported_lottery_types) != 1:
            raise ValueError("direct source binding requires one exact lottery type")
        lottery_type = identity.supported_lottery_types[0]
        if lottery_type is LotteryType.BIG_LOTTO:
            BigLottoReplayAdapter((binding,))
        elif lottery_type is LotteryType.DAILY_539:
            Daily539ReplayAdapter((binding,))
        elif lottery_type is LotteryType.POWER_LOTTO:
            PowerLottoReplayAdapter((binding,))
        else:  # pragma: no cover - LotteryType is a closed project enum.
            raise ValueError(f"unsupported lottery type {lottery_type.value}")
        return binding, None
    except Exception as exc:
        detail = str(exc).replace("\n", " ").strip() or "no detail"
        return None, f"{type(exc).__name__}: {detail[:240]}"


def _add_code_sources(
    items: dict[tuple[LotteryType, str, str | None], _MutableItem],
    code_identities: tuple[_CodeIdentity, ...],
) -> int:
    unresolved = 0
    for identity in code_identities:
        lottery_type = _code_identity_lottery(identity, items)
        if lottery_type is None:
            unresolved += 1
            continue
        locator = f"{identity.source_path}#{identity.class_name}"
        key = _identity_key(lottery_type, identity.strategy_id, identity.strategy_version)
        existing = items.get(key)
        status = identity.source_status or "CODE_PRESENT"
        direct_binding = None
        binding_error = None
        if (lottery_type, identity.strategy_id, identity.strategy_version) in (
            _DIRECT_CODE_BINDING_IDENTITIES
        ):
            direct_binding, binding_error = _direct_code_binding(identity)
        implementation_locator = (
            f"{identity.source_path.removesuffix('.py').replace('/', '.')}.{identity.class_name}"
        )
        if existing is not None:
            existing.add_source(
                _source_mapping(
                    kind="STRATEGY_ADAPTER_CODE",
                    locator=locator,
                    strategy_id=identity.strategy_id,
                    version=identity.strategy_version,
                    mapping="EXACT_LOTTERY_ID_AND_VERSION",
                    status=status,
                )
            )
            if direct_binding is not None and existing.adapter_mapping is None:
                existing.adapter_mapping = _primary_adapter_mapping(
                    direct_binding,
                    lottery_type,
                    implementation_locator,
                )
                existing.execution_capability = ReplayExecutionCapability.EXECUTABLE
                existing.replay_data_status = ReplayDataStatus.REBUILDABLE
                existing.reconstruction_reason = _direct_binding_reason(identity)
            continue

        data_status = (
            ReplayDataStatus.REBUILDABLE
            if direct_binding is not None
            else ReplayDataStatus.CODE_ONLY
        )
        capability = (
            ReplayExecutionCapability.EXECUTABLE
            if direct_binding is not None
            else ReplayExecutionCapability.UNAVAILABLE
        )
        mapping = (
            _primary_adapter_mapping(direct_binding, lottery_type, implementation_locator)
            if direct_binding is not None
            else None
        )
        lifecycle = ReplayLifecycleStatus.CODE_ONLY
        reason = (
            _direct_binding_reason(identity)
            if direct_binding is not None
            else "Source code has a stable id/version but no pinned production registry and "
            "Replay adapter identity. Code presence alone is not executable evidence."
        )
        if binding_error is not None:
            reason = f"{reason} Direct binding failed: {binding_error}"
        _add_item(
            items,
            lottery_type=lottery_type,
            strategy_id=identity.strategy_id,
            display_name=identity.strategy_name,
            strategy_version=identity.strategy_version,
            source_kind="CODE_ONLY",
            source_locator=locator,
            lifecycle_status=lifecycle,
            replay_data_status=data_status,
            execution_capability=capability,
            reconstruction_reason=reason,
            source=_source_mapping(
                kind="STRATEGY_ADAPTER_CODE",
                locator=locator,
                strategy_id=identity.strategy_id,
                version=identity.strategy_version,
                mapping="DIRECT_CODE_IDENTITY",
                status=status,
            ),
            adapter_mapping=mapping,
            source_statuses=(status,),
        )
    return unresolved


def _direct_binding_reason(identity: _CodeIdentity) -> str:
    if identity.strategy_id == "research_biglotto__quick_ml_corrected_successor_v1":
        return (
            "A deterministic Replay adapter wraps the checked-in successor implementation. "
            "The Backfill Engine still has no registered native binding for this identity."
        )
    if identity.strategy_id == "power_graph_synergy_seed42_2bet":
        return (
            "A deterministic Replay adapter wraps the checked-in Graph implementation, which "
            "currently supplies only its first zone. The Backfill Engine excludes it until a "
            "complete second-zone replay source is available."
        )
    return "An exact deterministic adapter was constructed from this pinned code identity."


def _add_first_batch_registry(
    items: dict[tuple[LotteryType, str, str | None], _MutableItem],
    full_catalog: FullStrategyCatalog,
) -> tuple[int, int]:
    source_identity_count = 0
    unresolved_identity_count = 0
    records_by_id = {record.strategy_id: record for record in full_catalog.records}
    mappings_by_id = {
        mapping.registry_strategy_id: mapping for mapping in full_catalog.first_batch_mappings
    }
    for strategy_id in full_catalog.first_batch_strategy_ids:
        source_identity_count += 1
        mapping = mappings_by_id[strategy_id]
        if mapping.catalog_strategy_id is not None:
            record = records_by_id.get(mapping.catalog_strategy_id)
            if record is not None:
                target = items.get(
                    _identity_key(
                        LotteryType.BIG_LOTTO, record.strategy_id, record.strategy_version
                    )
                )
                if target is None:
                    raise ValueError(
                        f"exact first-batch mapping target is absent: {record.strategy_id}"
                    )
                target.add_source(
                    _source_mapping(
                        kind="B649_REPLAY_BATCH_REGISTRY",
                        locator=(
                            f"{_FULL_CATALOG_LOCATOR}#first_batch.strategy_ids[{strategy_id}]"
                        ),
                        strategy_id=strategy_id,
                        version=record.strategy_version,
                        mapping="EXACT_SOURCE_SYMBOL_MATCH",
                        status=mapping.mapping_status.value,
                    )
                )
                target.source_statuses.add(mapping.mapping_status.value)
                continue
        unresolved_identity_count += 1
        locator = f"{_FULL_CATALOG_LOCATOR}#first_batch.strategy_ids[{strategy_id}]"
        _add_item(
            items,
            lottery_type=LotteryType.BIG_LOTTO,
            strategy_id=strategy_id,
            display_name=strategy_id,
            strategy_version=None,
            source_kind="B649_REPLAY_BATCH_REGISTRY",
            source_locator=locator,
            lifecycle_status=ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED,
            replay_data_status=ReplayDataStatus.NO_HISTORY,
            execution_capability=ReplayExecutionCapability.UNAVAILABLE,
            reconstruction_reason=mapping.mapping_reason,
            source=_source_mapping(
                kind="B649_REPLAY_BATCH_REGISTRY",
                locator=locator,
                strategy_id=strategy_id,
                version=None,
                mapping=mapping.mapping_status.value,
                status=mapping.mapping_status.value,
            ),
            source_statuses=(mapping.mapping_status.value,),
        )
    return source_identity_count, unresolved_identity_count


def _add_exact_native_artifact(
    items: dict[tuple[LotteryType, str, str | None], _MutableItem],
    payload: dict[str, object] | None,
) -> tuple[int, int]:
    if payload is None:
        return 0, 0
    unique: dict[tuple[str, str | None], dict[str, object]] = {}
    records = payload.get("records")
    if not isinstance(records, list):
        return 0, 0
    record_rows = cast(list[object], records)
    for row_value in record_rows:
        row = _as_json_object(row_value)
        if row is None:
            continue
        strategy_id = row.get("strategy_id")
        version = row.get("catalog_strategy_version") or row.get("strategy_version")
        if not isinstance(strategy_id, str):
            continue
        identity = (strategy_id, version if isinstance(version, str) else None)
        previous = unique.get(identity)
        status_counts = _as_json_object(row.get("replay_status_counts"))
        complete = status_counts.get("COMPLETE", 0) if status_counts is not None else 0
        previous_status_counts = (
            _as_json_object(previous.get("replay_status_counts")) if previous is not None else None
        )
        previous_complete_value = (
            previous_status_counts.get("COMPLETE", 0) if previous_status_counts is not None else 0
        )
        previous_complete = previous_complete_value if type(previous_complete_value) is int else -1
        if previous is None or (type(complete) is int and complete > previous_complete):
            unique[identity] = row

    for (strategy_id, version), row in unique.items():
        version_text = version or "UNKNOWN"
        locator = f"{_EXACT_NATIVE_LOCATOR}#strategy_id={strategy_id}&version={version_text}"
        status_counts = _as_json_object(row.get("replay_status_counts"))
        complete = status_counts.get("COMPLETE", 0) if status_counts is not None else 0
        execution_count = complete if type(complete) is int else 0
        key = _identity_key(LotteryType.BIG_LOTTO, strategy_id, version)
        item = items.get(key)
        if item is None:
            item = _add_item(
                items,
                lottery_type=LotteryType.BIG_LOTTO,
                strategy_id=strategy_id,
                display_name=str(row.get("display_name") or strategy_id),
                strategy_version=version,
                source_kind="HISTORICAL_REPLAY_ARTIFACT",
                source_locator=locator,
                lifecycle_status=ReplayLifecycleStatus.ARTIFACT_ONLY,
                replay_data_status=ReplayDataStatus.ARTIFACT_ONLY,
                execution_capability=ReplayExecutionCapability.ARTIFACT_ONLY,
                reconstruction_reason=(
                    "The packaged artifact contains aggregate replay/ranking evidence, but no "
                    "retained per-draw prediction rows or exact-version producer adapter."
                ),
                source=_source_mapping(
                    kind="HISTORICAL_REPLAY_ARTIFACT",
                    locator=locator,
                    strategy_id=strategy_id,
                    version=version,
                    mapping="ARTIFACT_ID_AND_VERSION",
                    status="AGGREGATE_REPLAY_PROJECTION",
                ),
                source_statuses=("AGGREGATE_REPLAY_PROJECTION",),
            )
        else:
            item.add_source(
                _source_mapping(
                    kind="HISTORICAL_REPLAY_ARTIFACT",
                    locator=locator,
                    strategy_id=strategy_id,
                    version=version,
                    mapping="EXACT_LOTTERY_ID_AND_VERSION",
                    status="AGGREGATE_REPLAY_PROJECTION",
                )
            )
        item.historical_execution_count = max(item.historical_execution_count, execution_count)
        item.historical_data_count = 0
    return len(unique), len(record_rows)


def _add_legacy_snapshot_only_rows(
    items: dict[tuple[LotteryType, str, str | None], _MutableItem],
    legacy_statuses: dict[tuple[str, str], str],
) -> int:
    catalog = production_catalog()
    catalog_identities = {
        (descriptor.strategy_id, descriptor.version, lottery_type)
        for descriptor in catalog
        for lottery_type in descriptor.lottery_types
    }
    count = 0
    for (strategy_id, version), lifecycle in legacy_statuses.items():
        if any(
            item_id == strategy_id and item_version == version
            for item_id, item_version, _ in catalog_identities
        ):
            continue
        # This frozen snapshot contains only historical lifecycle metadata.
        # Its rows remain visible without promoting those states to production.
        count += 1
        locator = f"{_LEGACY_SNAPSHOT_LOCATOR}#strategy_id={strategy_id}"
        _add_item(
            items,
            lottery_type=LotteryType.BIG_LOTTO,
            strategy_id=strategy_id,
            display_name=strategy_id,
            strategy_version=version,
            source_kind="LEGACY_CATALOG_SNAPSHOT",
            source_locator=locator,
            lifecycle_status=ReplayLifecycleStatus(lifecycle),
            replay_data_status=ReplayDataStatus.NO_HISTORY,
            execution_capability=ReplayExecutionCapability.UNAVAILABLE,
            reconstruction_reason=(
                f"The frozen snapshot records lifecycle {lifecycle}, but no current production "
                "descriptor, retained replay rows, or Replay adapter mapping exists."
            ),
            source=_source_mapping(
                kind="LEGACY_CATALOG_SNAPSHOT",
                locator=locator,
                strategy_id=strategy_id,
                version=version,
                mapping="FROZEN_SNAPSHOT_IDENTITY",
                status=lifecycle,
            ),
            source_statuses=(lifecycle,),
        )
    return count


def _model_state_is_missing(item: _MutableItem) -> bool:
    reason = item.reconstruction_reason.casefold()
    return "model" in reason and any(
        marker in reason for marker in ("missing", "not found", "unavailable", "does not exist")
    )


def _apply_execution_capabilities(
    items: Iterable[_MutableItem],
    native_binding_evidence: tuple[ReplayStrategyBindingEvidence, ...],
) -> None:
    """Add exact, source-backed Backfill facts without changing Inventory status."""

    evidence_by_identity: dict[
        tuple[LotteryType, str, str], list[ReplayStrategyBindingEvidence]
    ] = {}
    evidence_by_lottery_and_id: dict[tuple[LotteryType, str], set[str]] = {}
    for evidence in native_binding_evidence:
        evidence_by_identity.setdefault(evidence.identity, []).append(evidence)
        evidence_by_lottery_and_id.setdefault(
            (evidence.lottery_type, evidence.strategy_id), set()
        ).add(evidence.strategy_version)

    for item in items:
        identity_complete = item.strategy_version is not None
        model_state_missing = _model_state_is_missing(item)
        item.reconstructable = (
            None
            if not identity_complete or model_state_missing
            else item.replay_data_status
            in (ReplayDataStatus.REBUILDABLE, ReplayDataStatus.HAS_HISTORY)
        )
        item.wrapper_callable = (
            None
            if not identity_complete or model_state_missing
            else item.adapter_mapping is not None
        )

        if item.strategy_version is None:
            item.backfill_native_binding = None
            item.execution_block_reason = "SOURCE_IDENTITY_UNKNOWN: strategy_version is missing"
            continue

        exact_identity = (item.lottery_type, item.strategy_id, item.strategy_version)
        exact_evidence = evidence_by_identity.get(exact_identity, [])
        if exact_evidence:
            item.backfill_native_binding = True
            item.backfill_native_binding_sources = tuple(
                sorted(
                    set(exact_evidence),
                    key=lambda source: (source.source_kind, source.source_locator),
                )
            )
        elif evidence_by_lottery_and_id.get((item.lottery_type, item.strategy_id), set()):
            item.backfill_native_binding = None
            item.execution_block_reason = (
                "NATIVE_BINDING_VERSION_MISMATCH: current evidence has another strategy_version"
            )
        elif model_state_missing:
            item.backfill_native_binding = None
            item.execution_block_reason = "MODEL_STATE_UNKNOWN: required model state is unavailable"
        else:
            item.backfill_native_binding = False

        if item.execution_block_reason is not None:
            continue
        if item.backfill_native_binding is False:
            if item.strategy_id == "research_biglotto__quick_ml_corrected_successor_v1":
                item.execution_block_reason = "NO_CURRENT_NATIVE_BINDING"
            elif item.strategy_id == "power_graph_synergy_seed42_2bet":
                item.execution_block_reason = "NO_COMPLETE_SECOND_ZONE_REPLAY_SOURCE"
            elif item.lifecycle_status is ReplayLifecycleStatus.REJECTED:
                item.execution_block_reason = "SOURCE_REJECTED"
            elif item.replay_data_status is ReplayDataStatus.ARTIFACT_ONLY:
                item.execution_block_reason = "NO_REPLAYABLE_PREDICTION_SOURCE"
            else:
                item.execution_block_reason = "NO_CURRENT_NATIVE_BINDING"
            continue
        if model_state_missing:
            item.execution_block_reason = "MODEL_STATE_UNKNOWN: required model state is unavailable"
        elif item.reconstructable is not True:
            item.execution_block_reason = "NO_RECONSTRUCTABLE_REPLAY_DATA"
        elif item.wrapper_callable is not True:
            item.execution_block_reason = "NO_CALLABLE_REPLAY_WRAPPER"
        else:
            item.execution_block_reason = None


@dataclass(frozen=True, slots=True)
class _ImportedReplayIdentitySpec:
    lottery_type: LotteryType
    strategy_id: str
    display_name: str
    strategy_version: str
    source_locator: str
    reconstruction_reason: str
    source_status: str | None = None


_IMPORTED_HISTORY_ONLY_REASON = (
    "Historical coverage comes from the imported Replay Backfill run. "
    "No current native executable binding is registered."
)


_IMPORTED_REPLAY_IDENTITIES: tuple[_ImportedReplayIdentitySpec, ...] = (
    _ImportedReplayIdentitySpec(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id="research_biglotto__k9_optimal_coverage_candidate",
        display_name="大樂透 K9 最佳公平覆蓋候選研究策略",
        strategy_version="v0.1-research",
        source_locator=(
            "replay-backfill:d528aaecc35c4dae5e70a4330cfcd839d61345589f42fc6ac6fe06d9afb9c4a9"
        ),
        reconstruction_reason=_IMPORTED_HISTORY_ONLY_REASON,
        source_status="RESEARCH_STRATEGY",
    ),
    _ImportedReplayIdentitySpec(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id="research_biglotto__zone_momentum_complete_v1",
        display_name="Zone Momentum Complete",
        strategy_version="v1",
        source_locator=(
            "zone_successor_stage_642fb680b1a86e13c2594a6585b5c8f3776392936ff0681ac2b43f1846f73b5d"
        ),
        reconstruction_reason=(
            "Identified from imported Replay Backfill stage metadata; historical coverage "
            "comes strictly from Replay Backfill DB overlay with no current native executable "
            "binding."
        ),
    ),
    _ImportedReplayIdentitySpec(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id="evolution_h12_k30_geometry_completion",
        display_name="K30 Geometry (歷史研究策略)",
        strategy_version="v0.1",
        source_locator=(
            "src/lottolab/application/replay_strategy_inventory.py"
            "#evolution_h12_k30_geometry_completion"
        ),
        reconstruction_reason=(
            "Static K30 geometry research strategy identity; historical coverage comes strictly "
            "from Replay Backfill DB overlay with no current native executable binding."
        ),
        source_status="RESEARCH_STRATEGY",
    ),
    _ImportedReplayIdentitySpec(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id="evolution_h12_k30_matched_random_completion",
        display_name="K30 Matched Random (隨機補票對照組)",
        strategy_version="v0.1",
        source_locator=(
            "src/lottolab/application/replay_strategy_inventory.py"
            "#evolution_h12_k30_matched_random_completion"
        ),
        reconstruction_reason=(
            "Static K30 matched-random control baseline identity (non-production comparison "
            "reference only, not a future recommendation candidate); historical coverage comes "
            "strictly from Replay Backfill DB overlay with no current native executable binding."
        ),
        source_status="CONTROL_BASELINE",
    ),
    *(
        _ImportedReplayIdentitySpec(
            lottery_type=LotteryType.BIG_LOTTO,
            strategy_id=f"research_biglotto__submodular_sqrt_native_k{ticket_count}",
            display_name=f"K{ticket_count} Submodular Sqrt Native (歷史研究策略)",
            strategy_version="feature-sqrt-native-v1",
            source_locator=(
                "replay-backfill:988f6cc979a77e6f5227c0b0f7879fae98ab846de831b97b1e89947df9aa06bb"
            ),
            reconstruction_reason=_IMPORTED_HISTORY_ONLY_REASON,
            source_status="RESEARCH_STRATEGY",
        )
        for ticket_count in (6, 7, 8, 10, 11, 12, 25, 54)
    ),
    _ImportedReplayIdentitySpec(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id="research_biglotto__k5_cross_repaired_frozen_20261117_r1",
        display_name="K5 修正版 (現行補號)",
        strategy_version="v1.0.0",
        source_locator="replay-backfill:NUMBER2_A_K5_MATCHED_RANDOM_20261117_R1",
        reconstruction_reason=_IMPORTED_HISTORY_ONLY_REASON,
        source_status="RESEARCH_STRATEGY",
    ),
    _ImportedReplayIdentitySpec(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id="research_biglotto__k5_matched_random_frozen_20261117_r1",
        display_name="K5 修正版 (固定種子隨機基準)",
        strategy_version="v1.0.0",
        source_locator="replay-backfill:NUMBER2_A_K5_MATCHED_RANDOM_20261117_R1",
        reconstruction_reason=_IMPORTED_HISTORY_ONLY_REASON,
        source_status="CONTROL_BASELINE",
    ),
    _ImportedReplayIdentitySpec(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id="research_biglotto__k3_hedge_official_reference_20261117",
        display_name="K3 Hedge (歷史研究策略)",
        strategy_version="v1.0.0",
        source_locator=(
            "replay-backfill:4d9a74edeefa2d0953d47c9924b40c2d0a9f2d2f954ea9a48e17c60fb6c94fff"
        ),
        reconstruction_reason=_IMPORTED_HISTORY_ONLY_REASON,
        source_status="RESEARCH_STRATEGY",
    ),
    *(
        _ImportedReplayIdentitySpec(
            lottery_type=LotteryType.BIG_LOTTO,
            strategy_id=f"research_biglotto__k30_fixed_{pair_id}",
            display_name=f"K30 固定配對 {pair_id}",
            strategy_version="v1",
            source_locator=(
                "replay-backfill:3cdaab9ab5339e0b7433a68b6abf3103e268bd46fc089093e8a85dbee14c2c62"
            ),
            reconstruction_reason=_IMPORTED_HISTORY_ONLY_REASON,
            source_status="RESEARCH_STRATEGY",
        )
        for pair_id in ("414665013", "414671103")
    ),
    _ImportedReplayIdentitySpec(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id="research_biglotto__k30_fixed_random_control_20261119_r1",
        display_name="K30 固定種子隨機控制組 (歷史對照)",
        strategy_version="v1.0.0",
        source_locator=(
            "replay-backfill:befd9d8ec70c7cfe7d606511c42c9a7312deee1063800743488ad92cdcbb5543"
        ),
        reconstruction_reason=(
            "One fixed-seed portfolio used as a historical control; historical coverage comes "
            "from Replay Backfill DB overlay. No current native executable binding is registered."
        ),
        source_status="CONTROL_BASELINE",
    ),
    _ImportedReplayIdentitySpec(
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_id="research_biglotto__k3_cross_expert_fair_cover_20261119",
        display_name="K3 跨專家公平覆蓋",
        strategy_version="v1.0.0",
        source_locator=(
            "replay-backfill:bbcec3d72f8f1d7d9d124139f845a97e6ad6ea760d1b13fc9a9c6c0a71f8c82e"
        ),
        reconstruction_reason=_IMPORTED_HISTORY_ONLY_REASON,
        source_status="RESEARCH_STRATEGY",
    ),
    *(
        _ImportedReplayIdentitySpec(
            lottery_type=LotteryType.BIG_LOTTO,
            strategy_id=f"research_biglotto__prize_event_coverage_greedy_native_k{ticket_count}",
            display_name=f"K{ticket_count} 獎項事件貪婪覆蓋",
            strategy_version="prize-event-coverage-greedy-v1",
            source_locator=(
                "replay-backfill:91c7bad397d5dfbc20fccca42ae54bd6b8e398d6503273a855858b376ca78f16"
            ),
            reconstruction_reason=_IMPORTED_HISTORY_ONLY_REASON,
            source_status="RESEARCH_STRATEGY",
        )
        for ticket_count in (6, 7)
    ),
    *(
        _ImportedReplayIdentitySpec(
            lottery_type=LotteryType.POWER_LOTTO,
            strategy_id=f"research_powerlotto__historical_random_k{ticket_count}_20261119_r1",
            display_name=f"威力彩 K{ticket_count} 固定隨機控制",
            strategy_version="v1.0.0",
            source_locator=f"replay-backfill:{run_id}",
            reconstruction_reason=(
                "Fixed random control with a staged replay identity. "
                "The Replay Backfill store supplies historical coverage when available."
            ),
            source_status="CONTROL_BASELINE",
        )
        for ticket_count, run_id in (
            (1, "57aa0fe71cca7c6aa840d0423327aa799ebfc4dd266389274a26fd066d80a0c5"),
            (2, "51b2969442346a1821805dba35f02b4f959d4f8fc97d167e69445ca73d48b2b4"),
            (3, "b04551416d0c70c453f43b9c4c5caf84e15e3c28c48ca03f345213c696781dd2"),
            (4, "cb16f205477d79a13b9a0bbafe50dec30c4a8e2aea3c3d19d7285a7d12eca901"),
            (5, "368a10b154bdb557972c59fca65ea4cc6b8830951806c4b1fa2378c7e5de56b9"),
            (7, "69f95a62c28d8c9938197214526e7d91c5ccacf8924c76cef2fa005e33dabd4e"),
            (10, "0c59571af78ff53c50a061bf06faeb1435da36c9c7c486092e24120e169af1a4"),
            (11, "230077be87170ff97ce10dd233d12e96f1e2870780f949eea386ed41f3c9170d"),
            (12, "2614341c2b66bc1e4cb690752e38d4e82b770b920eb0d28101293c94ec401b44"),
            (25, "7928789e94bbac4aecc258b3bb2f6abbe6480c260d3cdc16d12caff16f54d814"),
        )
    ),
)

_IMPORTED_REPLAY_SOURCE_KIND = "REPLAY_BACKFILL_IMPORTED_RESULT"


def _add_imported_replay_identities(
    items: dict[tuple[LotteryType, str, str | None], _MutableItem],
) -> tuple[int, int]:
    """Register static imported replay-only strategy identities without fabrication."""

    for spec in _IMPORTED_REPLAY_IDENTITIES:
        source_statuses = (spec.source_status,) if spec.source_status is not None else ()
        _add_item(
            items,
            lottery_type=spec.lottery_type,
            strategy_id=spec.strategy_id,
            display_name=spec.display_name,
            strategy_version=spec.strategy_version,
            source_kind=_IMPORTED_REPLAY_SOURCE_KIND,
            source_locator=spec.source_locator,
            lifecycle_status=ReplayLifecycleStatus.UNREGISTERED_IDENTIFIED,
            replay_data_status=ReplayDataStatus.NO_HISTORY,
            execution_capability=ReplayExecutionCapability.UNAVAILABLE,
            reconstruction_reason=spec.reconstruction_reason,
            source=_source_mapping(
                kind=_IMPORTED_REPLAY_SOURCE_KIND,
                locator=spec.source_locator,
                strategy_id=spec.strategy_id,
                version=spec.strategy_version,
                mapping="exact_imported_replay_identity",
                status=spec.source_status,
            ),
            adapter_mapping=None,
            source_statuses=source_statuses,
        )
    count = len(_IMPORTED_REPLAY_IDENTITIES)
    return count, count


def _native_engine_evidence(
    items: dict[tuple[LotteryType, str, str | None], _MutableItem],
) -> tuple[ReplayStrategyBindingEvidence, ...]:
    """Use the same exact bindings the Backfill worker actually accepts."""
    evidence: list[ReplayStrategyBindingEvidence] = []
    for lottery_type in LotteryType:
        bindings, _accounts = native_strategy_inventory(lottery_type)
        for binding in bindings:
            strategy = binding.strategy
            key = _identity_key(lottery_type, strategy.strategy_id, strategy.strategy_version)
            if key not in items:
                implementation = binding.implementation
                _add_replay_binding_item(
                    items,
                    lottery_type=lottery_type,
                    binding=binding,
                    source_kind="NATIVE_BACKFILL_ENGINE",
                    source_locator="src/lottolab/application/native_replay_inventory.py",
                    implementation_locator=(
                        f"{type(implementation).__module__}.{type(implementation).__qualname__}"
                    ),
                )
            evidence.append(
                ReplayStrategyBindingEvidence(
                    lottery_type=lottery_type,
                    strategy_id=strategy.strategy_id,
                    strategy_version=strategy.strategy_version,
                    source_kind="NATIVE_BACKFILL_ENGINE",
                    source_locator=(
                        "src/lottolab/application/native_replay_inventory.py"
                        f"#strategy_id={strategy.strategy_id};version={strategy.strategy_version};"
                        f"fingerprint={strategy.fingerprint}"
                    ),
                )
            )
    return tuple(evidence)


@lru_cache(maxsize=1)
def load_replay_strategy_inventory(
    *,
    native_binding_evidence: tuple[ReplayStrategyBindingEvidence, ...] | None = None,
) -> ReplayStrategyInventory:
    """Build the deterministic index from packaged metadata and pinned adapters.

    This loader reads source catalogs and static evidence only.  It does not
    open a database, generate predictions, or modify production lifecycle.
    """

    production = production_catalog()
    descriptors = tuple(production)
    registry = ExecutableRegistry(production)
    full_catalog = load_full_strategy_catalog()
    legacy_statuses, legacy_row_count = _load_legacy_snapshot()
    (
        method_evidence,
        exact_batch_evidence,
        exact_native_evidence,
        evidence_file_count,
        _missing_evidence_files,
        source_integrity_issues,
        exact_native_payload,
    ) = _historical_evidence(full_catalog)
    items: dict[tuple[LotteryType, str, str | None], _MutableItem] = {}

    production_lineages = _add_production_items(
        items,
        descriptors,
        registry,
        legacy_statuses,
    )
    _add_full_catalog_items(
        items,
        full_catalog,
        method_evidence,
        exact_batch_evidence,
        exact_native_evidence,
        production_lineages,
    )

    t539_bindings = t539_replay_bindings()
    Daily539ReplayAdapter(t539_bindings)
    for binding in t539_bindings:
        implementation = binding.implementation
        implementation_locator = (
            f"{type(implementation).__module__}.{type(implementation).__qualname__}"
        )
        _add_replay_binding_item(
            items,
            lottery_type=LotteryType.DAILY_539,
            binding=binding,
            source_kind="T539_REPLAY_ADAPTER",
            source_locator="src/lottolab/application/historical_replay_adapters.py#t539_replay_bindings",
            implementation_locator=implementation_locator,
        )

    p638_adapter = PowerLottoReplayAdapter()
    p638_bindings = tuple(
        ReplayStrategyBinding(
            strategy=strategy,
            implementation=spec,
        )
        for strategy, spec in zip(
            p638_adapter.strategies,
            WAVE1_STRATEGIES,
            strict=True,
        )
    )
    for binding in p638_bindings:
        implementation = binding.implementation
        implementation_locator = (
            f"{type(implementation).__module__}.{type(implementation).__qualname__}"
        )
        _add_replay_binding_item(
            items,
            lottery_type=LotteryType.POWER_LOTTO,
            binding=binding,
            source_kind="P638_REPLAY_ADAPTER",
            source_locator="src/lottolab/application/historical_replay_adapters.py#PowerLottoReplayAdapter",
            implementation_locator=implementation_locator,
        )

    p638_wave2_bindings = tuple(binding_from_p638_spec(spec) for spec in WAVE2_STRATEGIES)
    for binding in p638_wave2_bindings:
        implementation = binding.implementation
        implementation_locator = (
            f"{type(implementation).__module__}.{type(implementation).__qualname__}"
        )
        _add_replay_binding_item(
            items,
            lottery_type=LotteryType.POWER_LOTTO,
            binding=binding,
            source_kind="P638_REPLAY_ADAPTER",
            source_locator="src/lottolab/strategies/adapters/powerlotto_wave2.py",
            implementation_locator=implementation_locator,
        )

    code_identities, code_class_row_count = _scan_adapter_code()
    if not any(
        identity.source_path == _POWER_GRAPH_CODE_IDENTITY.source_path
        and identity.class_name == _POWER_GRAPH_CODE_IDENTITY.class_name
        for identity in code_identities
    ):
        # This adapter stores its id and version in module constants, so the AST
        # scanner cannot recover them from class attributes.
        code_identities = (*code_identities, _POWER_GRAPH_CODE_IDENTITY)
        code_class_row_count += 1
    unresolved_code_sources = _add_code_sources(items, code_identities)
    first_batch_count, unresolved_batch_count = _add_first_batch_registry(items, full_catalog)
    exact_native_identity_count, exact_native_row_count = _add_exact_native_artifact(
        items,
        exact_native_payload,
    )
    _add_legacy_snapshot_only_rows(items, legacy_statuses)
    imported_identity_count, imported_row_count = _add_imported_replay_identities(items)

    engine_evidence = _native_engine_evidence(items)
    resolved_native_binding_evidence = (
        engine_evidence if native_binding_evidence is None else native_binding_evidence
    )
    if not all(
        type(evidence) is ReplayStrategyBindingEvidence
        for evidence in resolved_native_binding_evidence
    ):
        raise ValueError("native_binding_evidence contains an invalid binding identity")
    _apply_execution_capabilities(items.values(), tuple(resolved_native_binding_evidence))

    source_counts = (
        ReplayStrategySourceCount("PRODUCTION_CATALOG", len(descriptors), len(descriptors)),
        ReplayStrategySourceCount(
            "B649_RESEARCH_CATALOG", len(full_catalog.records), len(full_catalog.records)
        ),
        ReplayStrategySourceCount(
            "B649_REPLAY_ARTIFACT_SUMMARY",
            len(
                {
                    record.strategy_id
                    for record in full_catalog.records
                    if record.legacy_method_id in method_evidence
                    or (record.strategy_id, record.strategy_version) in exact_batch_evidence
                }
            ),
            len(
                {
                    record.strategy_id
                    for record in full_catalog.records
                    if record.legacy_method_id in method_evidence
                    or (record.strategy_id, record.strategy_version) in exact_batch_evidence
                }
            ),
            evidence_file_count,
        ),
        ReplayStrategySourceCount(
            "B649_REPLAY_BATCH_REGISTRY", first_batch_count, first_batch_count
        ),
        ReplayStrategySourceCount(
            "B649_EXACT_REPLAY_BATCH_EVIDENCE",
            len(exact_batch_evidence),
            len(exact_batch_evidence),
        ),
        ReplayStrategySourceCount("T539_REPLAY_ADAPTER", len(t539_bindings), len(t539_bindings)),
        ReplayStrategySourceCount(
            "P638_REPLAY_ADAPTER",
            len(p638_bindings) + len(p638_wave2_bindings),
            len(p638_bindings) + len(p638_wave2_bindings),
        ),
        ReplayStrategySourceCount(
            "STRATEGY_ADAPTER_CODE",
            len({(item.strategy_id, item.strategy_version) for item in code_identities}),
            code_class_row_count,
        ),
        ReplayStrategySourceCount(
            "LEGACY_CATALOG_SNAPSHOT",
            legacy_row_count,
            legacy_row_count,
        ),
        ReplayStrategySourceCount(
            "EXACT_NATIVE_RANKING_ARTIFACT",
            exact_native_identity_count,
            exact_native_row_count,
        ),
        ReplayStrategySourceCount(
            _IMPORTED_REPLAY_SOURCE_KIND,
            imported_identity_count,
            imported_row_count,
        ),
    )
    engine_identity_count = sum(
        any(source.source_kind == "NATIVE_BACKFILL_ENGINE" for source in item.sources.values())
        for item in items.values()
    )
    source_counts += (
        ReplayStrategySourceCount(
            "NATIVE_BACKFILL_ENGINE", engine_identity_count, engine_identity_count
        ),
    )
    ordered_items = tuple(
        sorted(
            (item.freeze() for item in items.values()),
            key=lambda item: (
                item.lottery_type.value,
                item.strategy_id,
                item.strategy_version or "",
                item.source_kind,
            ),
        )
    )
    return ReplayStrategyInventory(
        items=ordered_items,
        source_counts=source_counts,
        unresolved_source_count=unresolved_code_sources + unresolved_batch_count,
        source_integrity_issues=source_integrity_issues,
    )


__all__ = ["load_replay_strategy_inventory"]
