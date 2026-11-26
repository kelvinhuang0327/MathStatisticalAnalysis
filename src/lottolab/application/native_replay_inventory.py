"""Exact native Replay Backfill bindings shared by inventory and CLI."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import inspect
import random
from collections.abc import Callable
from dataclasses import asdict
from importlib.metadata import version as distribution_version
from pathlib import Path
from typing import Any, cast

from lottolab.application.historical_replay_adapters import (
    ReplayStrategyBinding,
    ReplayStrategyImplementation,
    binding_from_implementation,
    binding_from_p638_spec,
    t539_replay_bindings,
)
from lottolab.application.seeded_single_replay import SEED_CONTRACT, SeededSingleTicketReplay
from lottolab.application.use_cases.generate_bet import (
    instantiate_adapter,
    instantiate_portfolio_adapter,
)
from lottolab.application.use_cases.replay_backfill import JsonObject, identity
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayBehavior, ReplayStrategy
from lottolab.domain.strategies import ResponseShape
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.adapters.biglotto_batch16 import _EvolutionEngine
from lottolab.strategies.adapters.biglotto_causal_renewal_hazard import (
    ADAPTER_TYPES_BY_K as RENEWAL_HAZARD_ADAPTERS_BY_K,
)
from lottolab.strategies.adapters.biglotto_conditional_te import (
    BigLottoConditionalTEK2Adapter,
    BigLottoConditionalTEK3Adapter,
    BigLottoConditionalTEK5Adapter,
)
from lottolab.strategies.adapters.biglotto_evolution_bounded import BigLottoBoundedEvolutionAdapter
from lottolab.strategies.adapters.biglotto_evolution_causal import BigLottoCausalEvolutionAdapter
from lottolab.strategies.adapters.biglotto_evolution_strict import BigLottoStrictEvolutionAdapter
from lottolab.strategies.adapters.biglotto_quick_ml_pattern_bounds import (
    BigLottoQuickMlPatternBoundsAdapter,
)
from lottolab.strategies.adapters.biglotto_quickml_corrected_successor import (
    BigLottoQuickMlCorrectedSuccessorAdapter,
)
from lottolab.strategies.adapters.biglotto_wave12 import _quick_ml_hybrid
from lottolab.strategies.adapters.powerlotto_wave1 import WAVE1_STRATEGIES
from lottolab.strategies.adapters.powerlotto_wave2 import WAVE2_STRATEGIES
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

CONDITIONAL_TE_ADAPTERS_BY_K = {
    2: BigLottoConditionalTEK2Adapter,
    3: BigLottoConditionalTEK3Adapter,
    5: BigLottoConditionalTEK5Adapter,
}
_NATIVE_FINGERPRINT_COMMON_SOURCES = (
    "src/lottolab/application/native_replay_inventory.py",
    "src/lottolab/application/historical_replay_adapters.py",
    "src/lottolab/application/replay_strategy_inventory.py",
    "src/lottolab/domain/draws.py",
    "src/lottolab/domain/historical_replay.py",
    "src/lottolab/domain/lottery_rules.py",
    "src/lottolab/domain/prize_evaluation.py",
    "src/lottolab/strategies/adapters/base.py",
)
_NATIVE_FINGERPRINT_ALGORITHM_SOURCES = {
    "renewal_hazard": ("src/lottolab/strategies/adapters/biglotto_causal_renewal_hazard.py",),
    "conditional_te": ("src/lottolab/strategies/adapters/biglotto_conditional_te.py",),
}


def _native_implementation_fingerprint(
    implementation: ReplayStrategyImplementation,
    *,
    algorithm: str,
) -> tuple[str, dict[str, str], dict[str, str]]:
    """Fingerprint one exact adapter against its native Replay contracts."""

    try:
        algorithm_sources = _NATIVE_FINGERPRINT_ALGORITHM_SOURCES[algorithm]
    except KeyError as exc:
        raise ValueError(f"unsupported native fingerprint algorithm: {algorithm}") from exc

    project_root = Path(__file__).resolve().parents[3]
    source_hashes: dict[str, str] = {}
    for relative_path in (*_NATIVE_FINGERPRINT_COMMON_SOURCES, *algorithm_sources):
        source_path = project_root / relative_path
        if not source_path.is_file():
            raise ValueError(
                f"native implementation fingerprint source is unavailable: {relative_path}"
            )
        source_hashes[relative_path] = hashlib.sha256(source_path.read_bytes()).hexdigest()

    runtime_dependencies = (
        {"numpy": distribution_version("numpy")} if algorithm == "conditional_te" else {}
    )
    strategy = {
        "contract": "NATIVE_REPLAY_IMPLEMENTATION_FINGERPRINT_V1",
        "algorithm": algorithm,
        "strategy_id": implementation.strategy_id,
        "strategy_version": implementation.strategy_version,
        "native_ticket_count": implementation.native_ticket_count,
        "min_history": implementation.min_history,
        "behavior": ReplayBehavior.DETERMINISTIC.value,
        "source_sha256": source_hashes,
        "runtime_dependencies": runtime_dependencies,
    }
    return identity(strategy), source_hashes, runtime_dependencies


def native_strategy_inventory(
    lottery_type: LotteryType,
) -> tuple[tuple[ReplayStrategyBinding, ...], JsonObject]:
    """Account for every current catalog identity and every native replay binding.

    P638's complete replay specs retain genuine second-zone history. A catalog
    bridge which only emits a first-zone ticket is explicitly excluded unless
    an existing complete native spec supplies that same identity/version.
    """
    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    bindings: dict[str, ReplayStrategyBinding] = {}
    accounts: JsonObject = {}
    fingerprint_sources_by_strategy: dict[str, dict[str, str]] = {}
    fingerprint_dependencies_by_strategy: dict[str, dict[str, str]] = {}
    if lottery_type is LotteryType.BIG_LOTTO:
        implementation = BigLottoQuickMlPatternBoundsAdapter()
        candidate_source = inspect.getsourcefile(type(implementation))
        successor_source = inspect.getsourcefile(BigLottoQuickMlCorrectedSuccessorAdapter)
        hybrid_source = inspect.getsourcefile(_quick_ml_hybrid)
        if candidate_source is None or successor_source is None or hybrid_source is None:
            raise ValueError("Quick ML candidate dependency source is unavailable")
        # The replay was produced before the lint-only marker was added. Strip
        # that marker so its source identity remains stable across this edit.
        candidate_bytes = Path(candidate_source).read_bytes().replace(b"  # noqa: RUF001", b"")
        fingerprint = identity(
            {
                "candidate_adapter_sha256": hashlib.sha256(candidate_bytes).hexdigest(),
                "successor_sha256": hashlib.sha256(Path(successor_source).read_bytes()).hexdigest(),
                "wave12_sha256": hashlib.sha256(Path(hybrid_source).read_bytes()).hexdigest(),
            }
        )
        binding = binding_from_implementation(implementation, fingerprint=fingerprint)
        bindings[binding.strategy.strategy_id] = binding
        for ticket_count, adapter_type in sorted(RENEWAL_HAZARD_ADAPTERS_BY_K.items()):
            renewal_implementation = adapter_type()
            if renewal_implementation.native_ticket_count != ticket_count:
                raise ValueError("Renewal Hazard adapter K does not match its inventory key")
            fingerprint, source_hashes, runtime_dependencies = _native_implementation_fingerprint(
                renewal_implementation,
                algorithm="renewal_hazard",
            )
            renewal_binding = binding_from_implementation(
                renewal_implementation,
                behavior=ReplayBehavior.DETERMINISTIC,
                fingerprint=fingerprint,
            )
            if renewal_binding.strategy.strategy_id in bindings:
                raise ValueError(
                    f"duplicate native BIG_LOTTO strategy id: "
                    f"{renewal_binding.strategy.strategy_id}"
                )
            bindings[renewal_binding.strategy.strategy_id] = renewal_binding
            fingerprint_sources_by_strategy[renewal_binding.strategy.strategy_id] = source_hashes
            fingerprint_dependencies_by_strategy[renewal_binding.strategy.strategy_id] = (
                runtime_dependencies
            )
        for ticket_count, adapter_type in sorted(CONDITIONAL_TE_ADAPTERS_BY_K.items()):
            te_implementation = adapter_type()
            if te_implementation.native_ticket_count != ticket_count:
                raise ValueError("Conditional TE adapter K does not match its inventory key")
            fingerprint, source_hashes, runtime_dependencies = _native_implementation_fingerprint(
                te_implementation,
                algorithm="conditional_te",
            )
            te_binding = binding_from_implementation(
                te_implementation,
                behavior=ReplayBehavior.DETERMINISTIC,
                fingerprint=fingerprint,
            )
            if te_binding.strategy.strategy_id in bindings:
                raise ValueError(
                    f"duplicate native BIG_LOTTO strategy id: {te_binding.strategy.strategy_id}"
                )
            bindings[te_binding.strategy.strategy_id] = te_binding
            fingerprint_sources_by_strategy[te_binding.strategy.strategy_id] = source_hashes
            fingerprint_dependencies_by_strategy[te_binding.strategy.strategy_id] = (
                runtime_dependencies
            )
    elif lottery_type is LotteryType.DAILY_539:
        for binding in t539_replay_bindings():
            bindings[binding.strategy.strategy_id] = binding
    elif lottery_type is LotteryType.POWER_LOTTO:
        for spec in (*WAVE1_STRATEGIES, *WAVE2_STRATEGIES):
            binding = binding_from_p638_spec(spec)
            bindings[binding.strategy.strategy_id] = binding
    for key, binding in bindings.items():
        implementation = binding.implementation
        source_file = inspect.getsourcefile(type(implementation))
        accounts[key] = {
            "status": "EXECUTABLE",
            "strategy_version": binding.strategy.strategy_version,
            "source": "EXISTING_TARGET_NATIVE_REPLAY_BINDING",
            "source_module": type(implementation).__module__,
            "source_sha256": hashlib.sha256(Path(source_file).read_bytes()).hexdigest()
            if source_file
            else None,
            "provenance": getattr(implementation, "provenance", None),
            "model_version_or_null": getattr(implementation, "model_version", None),
            "fingerprint": binding.strategy.fingerprint,
            "implementation_fingerprint_source_sha256": fingerprint_sources_by_strategy.get(
                key, {}
            ),
            "implementation_fingerprint_runtime_dependencies": (
                fingerprint_dependencies_by_strategy.get(key, {})
            ),
            "behavior": binding.strategy.behavior.value,
        }
    for descriptor in catalog.list(lottery_type=lottery_type):
        sid = descriptor.strategy_id
        provenance = list(descriptor.provenance)
        if sid in bindings:
            if bindings[sid].strategy.strategy_version != descriptor.version:
                raise ValueError(f"native/catalog version conflict: {sid}")
            accounts[sid]["catalog_provenance"] = provenance
            continue
        if not descriptor.executable:
            accounts[sid] = {
                "status": "EXCLUDED",
                "reason": "CATALOG_NOT_EXECUTABLE",
                "catalog_provenance": provenance,
            }
            continue
        if lottery_type is LotteryType.POWER_LOTTO:
            accounts[sid] = {
                "status": "EXCLUDED",
                "reason": "NO_COMPLETE_SECOND_ZONE_REPLAY_SOURCE",
                "catalog_provenance": provenance,
            }
            continue
        try:
            cls = registry.load_adapter(sid)
            implementation = (
                instantiate_adapter(sid, cls)
                if descriptor.response_shape is ResponseShape.SINGLE_TICKET
                else instantiate_portfolio_adapter(sid, cls)
            )
            if (
                implementation.strategy_id,
                implementation.strategy_name,
                implementation.strategy_version,
            ) != (sid, descriptor.strategy_name, descriptor.version):
                raise ValueError("adapter/catalog identity mismatch")
            count = getattr(implementation, "native_ticket_count", 1)
            if count != descriptor.native_ticket_count:
                raise ValueError("adapter/catalog native ticket count mismatch")
            source_file = inspect.getsourcefile(type(implementation))
            if source_file is None:
                raise ValueError("adapter source is unavailable")
            source_sha = hashlib.sha256(Path(source_file).read_bytes()).hexdigest()
            unseeded_live_rng = (
                lottery_type is LotteryType.BIG_LOTTO
                and descriptor.response_shape is ResponseShape.SINGLE_TICKET
                and "randomness:PROCESS_GLOBAL_UNSEEDED_MATH_RANDOM_EQUIVALENT" in provenance
            )
            behavior = getattr(implementation, "replay_behavior", ReplayBehavior.DETERMINISTIC)
            seed_contract = getattr(implementation, "replay_seed_contract", None)
            wrapper_sha: str | None = None
            if unseeded_live_rng:
                wrapper_file = inspect.getsourcefile(SeededSingleTicketReplay)
                if wrapper_file is None:
                    raise ValueError("seeded replay wrapper source is unavailable")
                wrapper_sha = hashlib.sha256(Path(wrapper_file).read_bytes()).hexdigest()
                implementation = SeededSingleTicketReplay(
                    sid,
                    descriptor.strategy_name,
                    descriptor.version,
                    descriptor.min_history,
                    cast(Callable[[random.Random], Any], cls),
                )
                behavior = ReplayBehavior.SEEDED_STOCHASTIC
                seed_contract = SEED_CONTRACT
            fingerprint_payload: dict[str, object] = {
                "descriptor": asdict(descriptor),
                "source": source_sha,
            }
            dependency_sha: dict[str, str] = {}
            if (
                sid == "legacy_biglotto__evolution_engine__3df019c31ce4"
                and implementation.strategy_version
                in {
                    "v0.3",
                    "v0.4",
                    "v0.5",
                }
            ):
                dependencies: list[type[object]] = [
                    cast(type[object], _EvolutionEngine),
                    BigLottoCausalEvolutionAdapter,
                ]
                if implementation.strategy_version in {"v0.4", "v0.5"}:
                    dependencies.append(BigLottoStrictEvolutionAdapter)
                if implementation.strategy_version == "v0.5":
                    dependencies.extend([BigLottoBoundedEvolutionAdapter, CausalDrawRow])
                for dependency in dependencies:
                    dependency_file = inspect.getsourcefile(dependency)
                    if dependency_file is None:
                        raise ValueError("evolution dependency source is unavailable")
                    dependency_sha[dependency.__module__] = hashlib.sha256(
                        Path(dependency_file).read_bytes()
                    ).hexdigest()
                fingerprint_payload["dependency_sha256"] = dependency_sha
            if seed_contract is not None:
                fingerprint_payload["seed_contract"] = seed_contract
            if unseeded_live_rng:
                fingerprint_payload.update(
                    {"seed_contract": seed_contract, "seed_wrapper_sha256": wrapper_sha}
                )
            strategy = ReplayStrategy(
                sid,
                descriptor.strategy_name,
                implementation.strategy_version,
                behavior,
                descriptor.native_ticket_count,
                max(descriptor.min_history, implementation.min_history),
                fingerprint=identity(fingerprint_payload),
                seed_contract=seed_contract,
            )
            bindings[sid] = ReplayStrategyBinding(strategy, implementation)
            accounts[sid] = {
                "status": "EXECUTABLE",
                "strategy_version": implementation.strategy_version,
                "source": descriptor.adapter_path,
                "source_sha256": source_sha,
                "dependency_sha256": dependency_sha,
                "seed_wrapper_sha256": wrapper_sha,
                "seed_contract": seed_contract,
                "behavior": behavior.value,
                "catalog_provenance": provenance,
                "model_version_or_null": None,
            }
        except Exception as exc:
            accounts[sid] = {
                "status": "BLOCKED",
                "reason": type(exc).__name__ + ": " + str(exc),
                "catalog_provenance": provenance,
            }
    descriptors = {item.strategy_id: item for item in catalog.list(lottery_type=lottery_type)}
    for strategy_id, binding in bindings.items():
        descriptor = descriptors.get(strategy_id)
        account = accounts[strategy_id]
        account["lifecycle_status"] = (
            descriptor.lifecycle_status.value if descriptor is not None else "UNREGISTERED"
        )
        account["data_status"] = "REBUILDABLE"
        account["source_kind"] = (
            "PRODUCTION_CATALOG" if descriptor is not None else "TARGET_NATIVE_REPLAY"
        )
        if (
            strategy_id == "legacy_biglotto__evolution_engine__3df019c31ce4"
            and binding.strategy.strategy_version in {"v0.2", "v0.3", "v0.4", "v0.5"}
        ):
            account["training_status"] = "CAUSAL_FIT_PER_TARGET"
            account["training_holdout_size"] = 50
        else:
            account["training_status"] = "NOT_TRAINABLE"
        account["source_identity"] = account.get("source_sha256") or binding.strategy.fingerprint
    return tuple(bindings[k] for k in sorted(bindings)), accounts
