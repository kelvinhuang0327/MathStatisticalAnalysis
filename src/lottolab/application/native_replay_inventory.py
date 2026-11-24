"""Exact native Replay Backfill bindings shared by inventory and CLI."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import hashlib
import inspect
import random
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from lottolab.application.historical_replay_adapters import (
    ReplayStrategyBinding,
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
