"""Task-owned exact-native BIG_LOTTO K2/K3 replay and ranking harness.

This harness deliberately keeps the replay evidence outside the production
research store.  ``replay`` reads only the named DRAW_DATA authority, writes a
closed target-level JSONL evidence stream, and then seals a manifest containing
all source, universe, target-window, and byte-fingerprint identities.
``rank`` reopens that stream, verifies the seal, and calculates projections
without importing or executing a strategy.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sqlite3
import subprocess
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any, Protocol, cast

from lottolab.application.legacy_source_native_portfolios_wave26 import (
    DEFAULT_SOURCE_NATIVE_WAVE26_USER_SEED,
    SOURCE_NATIVE_WAVE26_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD,
)
from lottolab.application.use_cases.generate_bet import instantiate_portfolio_adapter
from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.prize_evaluation import evaluate_lottery_prize
from lottolab.domain.strategies import ResponseShape, StrategyDescriptor
from lottolab.infrastructure.persistence.storage_authorities import (
    StorageAuthorityRegistry,
)
from lottolab.strategies.adapters.base import (
    BetAdapterExecution,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

RUN_ID = "B649_K2_K3_EXACT_NATIVE_FULL_REPLAY_R1"
EVIDENCE_SCHEMA = "B649_EXACT_NATIVE_TARGET_EVIDENCE_V1"
MANIFEST_SCHEMA = "B649_EXACT_NATIVE_REPLAY_SEALED_MANIFEST_V1"
RANKING_SCHEMA = "B649_EXACT_NATIVE_RANKING_PROJECTION_V1"
EVIDENCE_FILENAME = "target_evidence.jsonl"
MANIFEST_FILENAME = "sealed_manifest.json"
RANKING_FILENAME = "ranking.json"
WINDOWS: tuple[tuple[str, int], ...] = (
    ("RECENT_50", 50),
    ("RECENT_300", 300),
    ("RECENT_750", 750),
)
_PRIZE_ORDER = {
    "FIRST": 1,
    "SECOND": 2,
    "THIRD": 3,
    "FOURTH": 4,
    "FIFTH": 5,
    "SIXTH": 6,
    "SEVENTH": 7,
    "GENERAL": 8,
}


class ReplayTaskError(RuntimeError):
    """The exact-native replay contract cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class Draw:
    """One validated BIG_LOTTO draw from the canonical authority."""

    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]
    special_number: int

    @property
    def sort_key(self) -> tuple[date, int]:
        return self.draw_date, int(self.draw_number)

    def causal_row(self) -> CausalDrawRow:
        return CausalDrawRow(
            draw=self.draw_number,
            date=self.draw_date.isoformat(),
            numbers=self.main_numbers,
        )


@dataclass(frozen=True, slots=True)
class RuntimeBinding:
    descriptor: StrategyDescriptor
    implementation: object | None
    adapter_class_name: str | None
    binding_error: str | None


class _PortfolioRuntime(Protocol):
    def get_bets_with_emission(
        self,
        history: object,
        lottery_type: LotteryType,
    ) -> tuple[BetAdapterExecution, ...]: ...


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_bytes(_canonical_json_bytes(value))


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _source_freeze(repo: Path) -> dict[str, str]:
    status = _git(repo, "status", "--porcelain=v1", "-uall")
    if status:
        raise ReplayTaskError(
            "REPLAY_SOURCE_WORKTREE_NOT_CLEAN: " + status.replace("\n", " | ")
        )
    return {
        "branch": _git(repo, "branch", "--show-current"),
        "head": _git(repo, "rev-parse", "HEAD"),
        "tree": _git(repo, "rev-parse", "HEAD^{tree}"),
        "status": "clean",
    }


def _parse_numbers(raw: object, *, field: str) -> tuple[int, ...]:
    if type(raw) is not list:
        raise ReplayTaskError(f"DRAW_AUTHORITY_INVALID_{field}")
    raw_values = cast(list[object], raw)
    if not all(type(value) is int for value in raw_values):
        raise ReplayTaskError(f"DRAW_AUTHORITY_INVALID_{field}")
    numbers = tuple(cast(list[int], raw_values))
    if len(numbers) != BIG_LOTTO_RULE_CONTRACT.main_number_count:
        raise ReplayTaskError(f"DRAW_AUTHORITY_INVALID_{field}_COUNT")
    if numbers != tuple(sorted(numbers)) or len(set(numbers)) != len(numbers):
        raise ReplayTaskError(f"DRAW_AUTHORITY_INVALID_{field}_ORDER")
    if any(
        number < BIG_LOTTO_RULE_CONTRACT.main_number_min
        or number > BIG_LOTTO_RULE_CONTRACT.main_number_max
        for number in numbers
    ):
        raise ReplayTaskError(f"DRAW_AUTHORITY_INVALID_{field}_RANGE")
    return numbers


def _load_authoritative_draws(repo: Path) -> tuple[tuple[Draw, ...], dict[str, object]]:
    registry = StorageAuthorityRegistry.from_file(repository_root=repo)
    verification = registry.resolver().verify("DRAW_DATA", deep=True)
    path = verification.path
    if verification.passed is not True or path is None:
        raise ReplayTaskError(
            "B649_EXACT_NATIVE_REPLAY_DRAW_AUTHORITY_BLOCKED: "
            + (verification.error or "verification did not pass")
        )

    before_sha = _sha256_file(path)
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            connection.execute("PRAGMA query_only=ON")
            rows = connection.execute(
                "SELECT draw_number, draw_date, main_numbers_json, "
                "special_numbers_json FROM draws WHERE lottery_type = ? "
                "ORDER BY draw_date, CAST(draw_number AS INTEGER), draw_number",
                (LotteryType.BIG_LOTTO.value,),
            ).fetchall()
    except (OSError, sqlite3.DatabaseError) as exc:
        raise ReplayTaskError(
            "B649_EXACT_NATIVE_REPLAY_DRAW_AUTHORITY_BLOCKED: read-only query failed"
        ) from exc
    after_sha = _sha256_file(path)
    if before_sha != after_sha:
        raise ReplayTaskError(
            "B649_EXACT_NATIVE_REPLAY_DRAW_AUTHORITY_BLOCKED: "
            "authority changed during read"
        )

    draws: list[Draw] = []
    for row in rows:
        if len(row) != 4 or type(row[0]) is not str or type(row[1]) is not str:
            raise ReplayTaskError("DRAW_AUTHORITY_INVALID_ROW_SHAPE")
        try:
            draw_date = date.fromisoformat(row[1])
            raw_main = json.loads(row[2])
            raw_special = json.loads(row[3])
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ReplayTaskError("DRAW_AUTHORITY_INVALID_ROW_JSON") from exc
        main_numbers = _parse_numbers(raw_main, field="MAIN_NUMBERS")
        if type(raw_special) is not list:
            raise ReplayTaskError("DRAW_AUTHORITY_INVALID_SPECIAL_NUMBER")
        special_values = cast(list[object], raw_special)
        if (
            len(special_values) != 1
            or type(special_values[0]) is not int
            or not 1 <= special_values[0] <= 49
            or special_values[0] in main_numbers
        ):
            raise ReplayTaskError("DRAW_AUTHORITY_INVALID_SPECIAL_NUMBER")
        draws.append(
            Draw(
                draw_number=row[0],
                draw_date=draw_date,
                main_numbers=main_numbers,
                special_number=special_values[0],
            )
        )

    if not draws or tuple(sorted(draws, key=lambda draw: draw.sort_key)) != tuple(draws):
        raise ReplayTaskError("DRAW_AUTHORITY_NOT_CHRONOLOGICAL")
    draw_payload = [
        {
            "draw_date": draw.draw_date.isoformat(),
            "draw_number": draw.draw_number,
            "main_numbers": list(draw.main_numbers),
            "special_number": draw.special_number,
        }
        for draw in draws
    ]
    authority = verification.authority
    metadata: dict[str, object] = {
        "authority_id": authority.authority_id,
        "capability": authority.capability,
        "status": authority.status,
        "schema": authority.schema,
        "verification": {
            "exists": verification.exists,
            "schema_valid": verification.schema_valid,
            "query_only": verification.query_only,
            "integrity_ok": verification.integrity_ok,
            "passed": verification.passed,
        },
        "sha256_before": before_sha,
        "sha256_after": after_sha,
        "draw_count": len(draws),
        "first_draw": {
            "draw_number": draws[0].draw_number,
            "draw_date": draws[0].draw_date.isoformat(),
        },
        "last_draw": {
            "draw_number": draws[-1].draw_number,
            "draw_date": draws[-1].draw_date.isoformat(),
        },
        "draw_payload_sha256": _sha256_bytes(_canonical_json_bytes(draw_payload)),
    }
    return tuple(draws), metadata


def _descriptor_payload(descriptor: StrategyDescriptor) -> dict[str, object]:
    return {
        "strategy_id": descriptor.strategy_id,
        "display_name": descriptor.strategy_name,
        "version": descriptor.version,
        "lottery_types": [lottery_type.value for lottery_type in descriptor.lottery_types],
        "lifecycle_status": descriptor.lifecycle_status.value,
        "executable": descriptor.executable,
        "adapter_path": descriptor.adapter_path,
        "min_history": descriptor.min_history,
        "response_shape": descriptor.response_shape.value,
        "native_ticket_count": descriptor.native_ticket_count,
        "native_ticket_count_bounds": list(descriptor.native_ticket_count_bounds),
        "provenance": list(descriptor.provenance),
    }


def _catalog_freeze() -> tuple[tuple[StrategyDescriptor, ...], dict[str, object]]:
    catalog = production_catalog()
    biglotto = tuple(catalog.list(lottery_type=LotteryType.BIG_LOTTO))
    exact = tuple(
        descriptor
        for descriptor in biglotto
        if descriptor.response_shape is ResponseShape.PORTFOLIO
        and descriptor.native_ticket_count in (2, 3)
    )
    k2 = tuple(descriptor for descriptor in exact if descriptor.native_ticket_count == 2)
    k3 = tuple(descriptor for descriptor in exact if descriptor.native_ticket_count == 3)
    k2_ids = {descriptor.strategy_id for descriptor in k2}
    k3_ids = {descriptor.strategy_id for descriptor in k3}
    if len(k2) != 19 or len(k3) != 19 or k2_ids & k3_ids:
        raise ReplayTaskError("EXACT_NATIVE_UNIVERSE_CONTRACT_INVALID")
    all_payload = [_descriptor_payload(descriptor) for descriptor in biglotto]
    universe_payload = {
        "k2": [_descriptor_payload(descriptor) for descriptor in k2],
        "k3": [_descriptor_payload(descriptor) for descriptor in k3],
    }
    metadata: dict[str, object] = {
        "production_catalog_count": len(tuple(catalog)),
        "biglotto_descriptor_count": len(biglotto),
        "catalog_fingerprint": _sha256_bytes(_canonical_json_bytes(all_payload)),
        "k2_universe_fingerprint": _sha256_bytes(
            _canonical_json_bytes(universe_payload["k2"])
        ),
        "k3_universe_fingerprint": _sha256_bytes(
            _canonical_json_bytes(universe_payload["k3"])
        ),
        "k2_count": len(k2),
        "k3_count": len(k3),
        "intersection": sorted(k2_ids & k3_ids),
        "strategies": universe_payload,
    }
    return exact, metadata


def _target_windows(draws: tuple[Draw, ...]) -> dict[str, dict[str, object]]:
    windows: dict[str, dict[str, object]] = {}
    for name, size in WINDOWS:
        if len(draws) < size:
            raise ReplayTaskError(f"DRAW_AUTHORITY_INSUFFICIENT_FOR_{name}")
        selected = draws[-size:]
        draw_numbers = [draw.draw_number for draw in selected]
        if len(set(draw_numbers)) != size:
            raise ReplayTaskError(f"{name}_TARGET_SEQUENCE_NOT_UNIQUE")
        windows[name] = {
            "observations_required": size,
            "draw_numbers": draw_numbers,
            "first_target": draw_numbers[0],
            "last_target": draw_numbers[-1],
            "first_target_date": selected[0].draw_date.isoformat(),
            "last_target_date": selected[-1].draw_date.isoformat(),
        }
    return windows


def _history_fingerprint(history: tuple[Draw, ...]) -> str:
    payload = [
        {
            "draw_date": draw.draw_date.isoformat(),
            "draw_number": draw.draw_number,
            "main_numbers": list(draw.main_numbers),
            "special_number": draw.special_number,
        }
        for draw in history
    ]
    return _sha256_bytes(_canonical_json_bytes(payload))


def _short_exception(exc: Exception) -> str:
    return str(exc).replace("\n", " ").strip()


def _runtime_bindings(descriptors: Sequence[StrategyDescriptor]) -> tuple[RuntimeBinding, ...]:
    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    bindings: list[RuntimeBinding] = []
    for descriptor in descriptors:
        try:
            adapter_class = registry.load_adapter(descriptor.strategy_id)
            implementation = instantiate_portfolio_adapter(
                descriptor.strategy_id,
                adapter_class,
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
            actual_bounds = implementation.native_ticket_count_bounds()
            if actual_identity != expected_identity:
                raise ReplayTaskError("ADAPTER_IDENTITY_MISMATCH")
            if (
                getattr(implementation, "native_ticket_count", None)
                != descriptor.native_ticket_count
                or actual_bounds != descriptor.native_ticket_count_bounds
            ):
                raise ReplayTaskError("ADAPTER_NATIVE_TICKET_COUNT_MISMATCH")
            bindings.append(
                RuntimeBinding(
                    descriptor=descriptor,
                    implementation=implementation,
                    adapter_class_name=getattr(adapter_class, "__qualname__", str(adapter_class)),
                    binding_error=None,
                )
            )
        except Exception as exc:
            bindings.append(
                RuntimeBinding(
                    descriptor=descriptor,
                    implementation=None,
                    adapter_class_name=None,
                    binding_error=f"{type(exc).__name__}: {_short_exception(exc)}",
                )
            )
    return tuple(bindings)


_WAVE11_SEED_FIELDS: Mapping[str, tuple[str, str, str, str]] = {
    "legacy_biglotto__core_satellite__611284461323": (
        "_RANDOM_NATIVE_PROTOCOL",
        "_CORE_SATELLITE_METHOD_ID",
        "_CORE_SATELLITE_SOURCE_SHA256",
        "_RANDOM_NATIVE_DEFAULT_USER_SEED",
    ),
    "legacy_biglotto__zone_split__b6144f9d479f": (
        "_RANDOM_NATIVE_PROTOCOL",
        "_ZONE_SPLIT_METHOD_ID",
        "_ZONE_SPLIT_SOURCE_SHA256",
        "_RANDOM_NATIVE_DEFAULT_USER_SEED",
    ),
    "legacy_biglotto__big_lotto_exhaustive_audit__694d353b7ca2": (
        "_HISTORY_NATIVE_PROTOCOL",
        "_EXHAUSTIVE_AUDIT_METHOD_ID",
        "_EXHAUSTIVE_AUDIT_SOURCE_SHA256",
        "_HISTORY_NATIVE_DEFAULT_USER_SEED",
    ),
}
_WAVE26_METHODS: Mapping[str, str] = {
    "legacy_biglotto__test_ces__78d17c530ab8": "tools/test_ces.py",
    "legacy_biglotto__test_dms__b63442289bd5": "tools/test_dms.py",
    "legacy_biglotto__test_greedy_optimizer__82df7f878ece": "tools/test_greedy_optimizer.py",
    "legacy_biglotto__test_mwsc__ba37643d6a3b": "tools/test_mwsc.py",
}
_STATISTICAL_MODULES = frozenset(
    {
        "lottolab.strategies.adapters.biglotto_wave3",
        "lottolab.strategies.adapters.biglotto_wave4",
        "lottolab.strategies.adapters.biglotto_wave5",
        "lottolab.strategies.adapters.biglotto_wave6",
        "lottolab.strategies.adapters.biglotto_wave7",
        "lottolab.strategies.adapters.biglotto_wave8",
        "lottolab.strategies.adapters.biglotto_wave9",
        "lottolab.strategies.adapters.biglotto_wave13",
        "lottolab.strategies.adapters.biglotto_wave14",
        "lottolab.strategies.adapters.biglotto_batch15",
    }
)


def _seed_metadata(
    descriptor: StrategyDescriptor,
    history: tuple[CausalDrawRow, ...],
) -> dict[str, object]:
    module_name = (descriptor.adapter_path or "").split(":", 1)[0]
    metadata: dict[str, object] = {
        "behavior": "DETERMINISTIC",
        "seed": None,
        "rng_state_rule": "NONE_DETERMINISTIC",
        "configuration": "native_adapter_configuration",
        "prestate_dependency": "causal_history_only",
    }
    if descriptor.strategy_id in _WAVE11_SEED_FIELDS and history:
        module = importlib.import_module(module_name)
        protocol_name, method_name, source_name, user_seed_name = _WAVE11_SEED_FIELDS[
            descriptor.strategy_id
        ]
        target_fn = cast(
            Callable[[tuple[CausalDrawRow, ...]], str],
            module._target_after_causal_cutoff,
        )
        target_identity = target_fn(history)
        protocol = cast(str, getattr(module, protocol_name))
        method_id = cast(str, getattr(module, method_name))
        source_sha = cast(str, getattr(module, source_name))
        user_seed = cast(str, getattr(module, user_seed_name))
        material = "|".join((protocol, method_id, source_sha, target_identity, "0", user_seed))
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        metadata.update(
            {
                "behavior": "SEEDED_STOCHASTIC",
                "seed": str(int(digest, 16)),
                "seed_digest": digest,
                "seed_material": material,
                "rng_state_rule": "random.Random(seed_integer, version=2)",
                "configuration": protocol,
                "prestate_dependency": "last_causal_draw_identity_only",
            }
        )
        return metadata

    if (
        descriptor.strategy_id
        == "legacy_biglotto__constraint_filter_predictor__3a85b3995002"
        and history
    ):
        module = importlib.import_module(module_name)
        seed_fn = cast(Callable[[tuple[CausalDrawRow, ...]], int], module._seed_integer)
        target_fn = cast(
            Callable[[tuple[CausalDrawRow, ...]], str],
            module._target_after_causal_cutoff,
        )
        seed_integer = seed_fn(history)
        target_identity = target_fn(history)
        protocol = cast(str, module._HISTORY_NATIVE_WAVE2_PROTOCOL)
        method_id = cast(str, module._CONSTRAINT_FILTER_METHOD_ID)
        source_sha = cast(str, module._CONSTRAINT_FILTER_SOURCE_SHA256)
        user_seed = cast(str, module._HISTORY_NATIVE_WAVE2_DEFAULT_USER_SEED)
        material = "|".join((protocol, method_id, source_sha, target_identity, "0", user_seed))
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        metadata.update(
            {
                "behavior": "SEEDED_STOCHASTIC",
                "seed": str(seed_integer),
                "seed_digest": digest,
                "seed_material": material,
                "rng_state_rule": (
                    "legacy NumPy RandomState(seed % 2**32) + "
                    "random.Random(seed, version=2)"
                ),
                "configuration": protocol,
                "prestate_dependency": "last_causal_draw_identity_only",
            }
        )
        return metadata

    if descriptor.strategy_id in _WAVE26_METHODS and history:
        method_id = _WAVE26_METHODS[descriptor.strategy_id]
        module_name_wave8 = "lottolab.strategies.adapters.biglotto_wave8"
        wave8 = importlib.import_module(module_name_wave8)
        target_fn = cast(
            Callable[[tuple[CausalDrawRow, ...]], str],
            wave8._target_after_causal_cutoff,
        )
        target_identity = target_fn(history)
        source_sha = SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD[method_id]
        material = "|".join(
            (
                SOURCE_NATIVE_WAVE26_PROTOCOL,
                method_id,
                source_sha,
                target_identity,
                "0",
                DEFAULT_SOURCE_NATIVE_WAVE26_USER_SEED,
            )
        )
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        metadata.update(
            {
                "behavior": "SEEDED_STOCHASTIC",
                "seed": str(int(digest, 16)),
                "seed_digest": digest,
                "seed_material": material,
                "rng_state_rule": (
                    "wave26 frozen statistical calls reseed from "
                    "causal history length"
                ),
                "configuration": SOURCE_NATIVE_WAVE26_PROTOCOL,
                "prestate_dependency": "last_causal_draw_identity_and_causal_history",
            }
        )
        return metadata

    if module_name in _STATISTICAL_MODULES:
        metadata.update(
            {
                "behavior": "SEEDED_STOCHASTIC",
                "seed": len(history),
                "rng_state_rule": (
                    "random.Random(len(causal_history)) inside frozen "
                    "statistical predictor"
                ),
                "configuration": "UNIFIED_STATISTICAL_HISTORY_LENGTH_SEED",
                "prestate_dependency": "causal_history_length_only",
            }
        )
        if descriptor.strategy_id == "legacy_biglotto__test_zdp__e80cc7e95453":
            metadata["rng_state_rule"] = (
                "random.Random(len(causal_history)) for statistical pool; "
                "random.seed(42) before each fallback"
            )
            metadata["fallback_seed"] = 42
        return metadata

    if descriptor.strategy_id == "legacy_biglotto__biglotto_diversified_ensemble_v6__8caaac8fcb5d":
        metadata.update(
            {
                "behavior": "SEEDED_STOCHASTIC",
                "seed": 42,
                "rng_state_rule": (
                    "local random.Random(42) per adapter call; "
                    "NumPy seed is output-inert"
                ),
                "configuration": "DIVERSIFIED_ENSEMBLE_V6_FIXED_SEED",
                "prestate_dependency": "causal_history_only",
            }
        )
    return metadata


def _base_evidence_row(
    descriptor: StrategyDescriptor,
    target: Draw,
    history: tuple[Draw, ...],
    windows: Mapping[str, Mapping[str, object]],
    seed_metadata: Mapping[str, object],
) -> dict[str, object]:
    cutoff = history[-1] if history else None
    window_names = [
        name
        for name, window in windows.items()
        if target.draw_number in cast(list[str], window["draw_numbers"])
    ]
    return {
        "schema_version": EVIDENCE_SCHEMA,
        "run_id": RUN_ID,
        "strategy_id": descriptor.strategy_id,
        "display_name": descriptor.strategy_name,
        "strategy_version": descriptor.version,
        "native_ticket_count": descriptor.native_ticket_count,
        "target_draw_number": target.draw_number,
        "target_draw_date": target.draw_date.isoformat(),
        "actual_main_numbers": list(target.main_numbers),
        "actual_special_number": target.special_number,
        "causal_cutoff_draw_number": cutoff.draw_number if cutoff else None,
        "causal_cutoff_date": cutoff.draw_date.isoformat() if cutoff else None,
        "causal_history_length": len(history),
        "causal_history_fingerprint": _history_fingerprint(history),
        "target_outcome_excluded": target not in history,
        "window_names": window_names,
        "seed_metadata": dict(seed_metadata),
    }


def _failure_row(
    base: dict[str, object],
    *,
    status: str,
    reason: str,
) -> dict[str, object]:
    return {
        **base,
        "replay_status": status,
        "reason": reason,
        "pre_eligible": status != "WINDOW_INELIGIBLE_INCOMPLETE_OBSERVATIONS",
        "actual_native_ticket_count": None,
        "native_emitted_portfolio": None,
        "native_portfolio": None,
        "ticket_evaluations": None,
        "official_any_prize": None,
        "best_official_prize": None,
    }


def _complete_row(
    base: dict[str, object],
    executions: tuple[BetAdapterExecution, ...],
    target: Draw,
) -> dict[str, object]:
    evaluations: list[dict[str, object]] = []
    for position, execution in enumerate(executions, start=1):
        outcome = evaluate_lottery_prize(
            lottery_type=LotteryType.BIG_LOTTO,
            predicted_main_numbers=execution.legal_main_numbers,
            predicted_special_number=execution.special_number,
            winning_main_numbers=target.main_numbers,
            winning_special_number=target.special_number,
        )
        evaluations.append(
            {
                "ticket_position": position,
                "emitted_main_numbers": list(execution.emitted_main_numbers),
                "predicted_main_numbers": list(execution.legal_main_numbers),
                "predicted_special_number": execution.special_number,
                "main_hits": outcome.zone1_hits,
                "special_hit": outcome.zone2_hit,
                "is_winner": outcome.is_winner,
                "official_prize": outcome.prize_tier,
            }
        )
    winners = [
        value
        for value in evaluations
        if cast(bool, value["is_winner"])
    ]
    best_prize = min(
        (cast(str, value["official_prize"]) for value in winners),
        key=lambda prize: _PRIZE_ORDER[prize],
        default=None,
    )
    return {
        **base,
        "replay_status": "COMPLETE",
        "reason": None,
        "pre_eligible": True,
        "actual_native_ticket_count": len(executions),
        "native_emitted_portfolio": [value["emitted_main_numbers"] for value in evaluations],
        "native_portfolio": [value["predicted_main_numbers"] for value in evaluations],
        "ticket_evaluations": evaluations,
        "official_any_prize": bool(winners),
        "best_official_prize": best_prize,
    }


def _assert_causal_history(target: Draw, history: Sequence[Draw]) -> None:
    """Reject any history row at or after the target draw's ordering key."""

    if any(draw.sort_key >= target.sort_key for draw in history):
        raise ReplayTaskError(
            f"CAUSAL_CUTOFF_VIOLATION before target {target.draw_number}"
        )


def _replay_cell(
    binding: RuntimeBinding,
    target: Draw,
    history: tuple[Draw, ...],
    windows: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    causal_rows = tuple(draw.causal_row() for draw in history)
    seed_metadata = _seed_metadata(binding.descriptor, causal_rows)
    base = _base_evidence_row(binding.descriptor, target, history, windows, seed_metadata)
    if binding.binding_error is not None:
        return _failure_row(
            base,
            status="EXECUTION_FAILURE",
            reason=f"BINDING_FAILURE: {binding.binding_error}",
        )
    if len(history) < binding.descriptor.min_history:
        return _failure_row(
            base,
            status="WINDOW_INELIGIBLE_INCOMPLETE_OBSERVATIONS",
            reason=(
                f"required causal history {binding.descriptor.min_history}, "
                f"available {len(history)}"
            ),
        )
    implementation = binding.implementation
    if implementation is None:
        return _failure_row(base, status="EXECUTION_FAILURE", reason="BINDING_FAILURE")
    try:
        get_bets = cast(_PortfolioRuntime, implementation).get_bets_with_emission
        executions = get_bets(causal_rows, LotteryType.BIG_LOTTO)
        if type(executions) is not tuple:
            raise TypeError("adapter did not return a tuple of ticket executions")
        if len(executions) != binding.descriptor.native_ticket_count:
            return _failure_row(
                base,
                status="NATIVE_TICKET_COUNT_VIOLATION",
                reason=(
                    f"expected {binding.descriptor.native_ticket_count} native tickets, "
                    f"got {len(executions)}"
                ),
            )
        return _complete_row(base, executions, target)
    except InsufficientHistory as exc:
        return _failure_row(
            base,
            status="WINDOW_INELIGIBLE_INCOMPLETE_OBSERVATIONS",
            reason=f"{type(exc).__name__}: {_short_exception(exc)}",
        )
    except InvalidOutput as exc:
        reason = f"{type(exc).__name__}: {_short_exception(exc)}"
        status = (
            "NATIVE_TICKET_COUNT_VIOLATION"
            if "native ticket" in reason.lower()
            else "EXECUTION_FAILURE"
        )
        return _failure_row(base, status=status, reason=reason)
    except Exception as exc:
        return _failure_row(
            base,
            status="EXECUTION_FAILURE",
            reason=f"{type(exc).__name__}: {_short_exception(exc)}",
        )


def _coverage_summary(
    rows: Sequence[Mapping[str, object]],
    descriptors: Sequence[StrategyDescriptor],
) -> dict[str, object]:
    by_strategy: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        by_strategy[cast(str, row["strategy_id"])].append(row)
    summary: dict[str, object] = {}
    for descriptor in descriptors:
        status_counts = Counter(
            cast(str, row["replay_status"]) for row in by_strategy[descriptor.strategy_id]
        )
        reasons = Counter(
            cast(str, row["reason"])
            for row in by_strategy[descriptor.strategy_id]
            if row["reason"] is not None
        )
        summary[descriptor.strategy_id] = {
            "native_ticket_count": descriptor.native_ticket_count,
            "display_name": descriptor.strategy_name,
            "record_count": len(by_strategy[descriptor.strategy_id]),
            "status_counts": dict(sorted(status_counts.items())),
            "typed_reasons": dict(sorted(reasons.items())),
        }
    return summary


def run_replay(output_dir: Path) -> dict[str, object]:
    """Execute all current exact-native cells and seal target-level evidence."""

    if output_dir.exists():
        raise ReplayTaskError(f"output directory already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    repo = Path(__file__).resolve().parents[1]
    source = _source_freeze(repo)
    descriptors, universe = _catalog_freeze()
    draws, authority = _load_authoritative_draws(repo)
    windows = _target_windows(draws)
    latest_window = cast(list[str], windows["RECENT_750"]["draw_numbers"])
    draw_by_number = {draw.draw_number: draw for draw in draws}
    index_by_number = {draw.draw_number: index for index, draw in enumerate(draws)}
    bindings = _runtime_bindings(descriptors)
    evidence_path = output_dir / EVIDENCE_FILENAME
    rows: list[dict[str, object]] = []
    with evidence_path.open("x", encoding="utf-8", newline="\n") as handle:
        for target_number in latest_window:
            target = draw_by_number[target_number]
            target_index = index_by_number[target_number]
            history = draws[:target_index]
            _assert_causal_history(target, history)
            for binding in bindings:
                row = _replay_cell(binding, target, history, windows)
                handle.write(
                    json.dumps(
                        row,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    + "\n"
                )
                rows.append(row)

    evidence_sha = _sha256_file(evidence_path)
    evidence_bytes = evidence_path.stat().st_size
    authority_after = _sha256_file(
        StorageAuthorityRegistry.from_file(repository_root=repo)
        .resolver()
        .resolve("DRAW_DATA")
        .require_path()
    )
    if authority_after != cast(str, authority["sha256_before"]):
        raise ReplayTaskError("INPUT_DATA_MUTATED_DURING_REPLAY")

    manifest: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA,
        "run_id": RUN_ID,
        "source": source,
        "catalog": universe,
        "draw_authority": authority,
        "target_windows": windows,
        "execution_contract": {
            "lottery_type": LotteryType.BIG_LOTTO.value,
            "history_order": "ASCENDING_DRAW_DATE_THEN_NUMERIC_DRAW_NUMBER",
            "target_outcome_excluded": True,
            "causal_rule": "all history rows have sort_key strictly less than target sort_key",
            "portfolio_contract": (
                "exact descriptor native_ticket_count; no truncation, extension, "
                "duplication, or padding"
            ),
            "primary_metric": "OFFICIAL_ANY_PRIZE at distinct target-draw level",
            "ranking_tie_break": [
                "OFFICIAL_ANY_PRIZE_RATE_DESC",
                "SUCCESSFUL_DRAWS_DESC",
                "STRATEGY_ID_ASC",
            ],
            "deterministic_replay": "native adapter-owned seed/state rules recorded per target row",
        },
        "evidence": {
            "file": EVIDENCE_FILENAME,
            "schema_version": EVIDENCE_SCHEMA,
            "writer_closed_before_seal": True,
            "sha256": evidence_sha,
            "byte_size": evidence_bytes,
            "record_count": len(rows),
            "status_counts": dict(
                sorted(Counter(cast(str, row["replay_status"]) for row in rows).items())
            ),
            "strategy_coverage": _coverage_summary(rows, descriptors),
        },
        "universe": {
            "k2_strategy_ids": [
                descriptor.strategy_id
                for descriptor in descriptors
                if descriptor.native_ticket_count == 2
            ],
            "k3_strategy_ids": [
                descriptor.strategy_id
                for descriptor in descriptors
                if descriptor.native_ticket_count == 3
            ],
            "attempted_strategy_count": len(descriptors),
            "attempted_target_count_per_strategy": len(latest_window),
            "attempted_cell_count": len(rows),
        },
        "seal": {
            "sealed_before_ranking": True,
            "ranking_must_reopen_read_only": True,
            "production_research_store_promotion": "NOT_RUN",
        },
    }
    _write_json(output_dir / MANIFEST_FILENAME, manifest)
    return manifest


def _load_sealed_bundle(
    evidence_dir: Path,
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...], str]:
    manifest_path = evidence_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ReplayTaskError("SEALED_MANIFEST_MISSING")
    manifest_raw = manifest_path.read_bytes()
    manifest = cast(dict[str, Any], json.loads(manifest_raw))
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ReplayTaskError("SEALED_MANIFEST_SCHEMA_MISMATCH")
    evidence_name = manifest.get("evidence", {}).get("file")
    if type(evidence_name) is not str or Path(evidence_name).name != evidence_name:
        raise ReplayTaskError("SEALED_EVIDENCE_LOCATOR_INVALID")
    evidence_path = evidence_dir / evidence_name
    if not evidence_path.is_file():
        raise ReplayTaskError("SEALED_EVIDENCE_MISSING")
    expected_sha = manifest["evidence"].get("sha256")
    expected_bytes = manifest["evidence"].get("byte_size")
    actual_sha = _sha256_file(evidence_path)
    actual_bytes = evidence_path.stat().st_size
    if actual_sha != expected_sha or actual_bytes != expected_bytes:
        raise ReplayTaskError("SEALED_EVIDENCE_FINGERPRINT_MISMATCH")
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    with evidence_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                row = cast(dict[str, Any], json.loads(line))
            except json.JSONDecodeError as exc:
                raise ReplayTaskError(f"SEALED_EVIDENCE_INVALID_JSON_LINE_{line_number}") from exc
            if row.get("schema_version") != EVIDENCE_SCHEMA:
                raise ReplayTaskError("SEALED_EVIDENCE_SCHEMA_MISMATCH")
            key = (cast(str, row["strategy_id"]), cast(str, row["target_draw_number"]))
            if key in seen:
                raise ReplayTaskError(f"SEALED_EVIDENCE_DUPLICATE_CELL_{key[0]}_{key[1]}")
            seen.add(key)
            rows.append(row)
    if len(rows) != manifest["evidence"].get("record_count"):
        raise ReplayTaskError("SEALED_EVIDENCE_RECORD_COUNT_MISMATCH")
    return manifest, tuple(rows), _sha256_bytes(manifest_raw)


def _metric_row(
    descriptor: Mapping[str, Any],
    complete_rows: Sequence[Mapping[str, Any]],
    *,
    first_target: str,
    last_target: str,
    observations_required: int,
) -> dict[str, object]:
    successful = sum(bool(row["official_any_prize"]) for row in complete_rows)
    best_prize = min(
        (
            cast(str, row["best_official_prize"])
            for row in complete_rows
            if row["best_official_prize"] is not None
        ),
        key=lambda prize: _PRIZE_ORDER[prize],
        default=None,
    )
    fraction = Fraction(successful, len(complete_rows))
    return {
        "strategy_id": descriptor["strategy_id"],
        "display_name": descriptor["display_name"],
        "native_ticket_count": descriptor["native_ticket_count"],
        "successful_draws": successful,
        "observations": len(complete_rows),
        "observations_required": observations_required,
        "official_any_prize_rate": f"{successful / len(complete_rows):.12f}",
        "official_any_prize_fraction": f"{fraction.numerator}/{fraction.denominator}",
        "first_target": first_target,
        "last_target": last_target,
        "best_official_prize": best_prize,
    }


def _rank_from_rows(
    manifest: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    catalog_strategies = cast(Mapping[str, Any], manifest["catalog"])["strategies"]
    k2_descriptors = cast(
        list[Mapping[str, Any]],
        cast(Mapping[str, Any], catalog_strategies)["k2"],
    )
    k3_descriptors = cast(
        list[Mapping[str, Any]],
        cast(Mapping[str, Any], catalog_strategies)["k3"],
    )
    descriptors_by_id = {
        cast(str, descriptor["strategy_id"]): descriptor
        for descriptor in (*k2_descriptors, *k3_descriptors)
    }
    category_ids = {
        "K2": tuple(cast(list[str], manifest["universe"]["k2_strategy_ids"])),
        "K3": tuple(cast(list[str], manifest["universe"]["k3_strategy_ids"])),
    }
    rows_by_key = {
        (cast(str, row["strategy_id"]), cast(str, row["target_draw_number"])): row
        for row in rows
    }
    leaderboards: dict[str, object] = {}
    coverage: dict[str, object] = {}
    for category, strategy_ids in category_ids.items():
        category_windows: dict[str, object] = {}
        category_coverage: dict[str, object] = {}
        for strategy_id in strategy_ids:
            strategy_coverage: dict[str, object] = {}
            for window_name, _size in WINDOWS:
                window = cast(Mapping[str, Any], manifest["target_windows"][window_name])
                target_numbers = tuple(cast(list[str], window["draw_numbers"]))
                expected = [
                    rows_by_key.get((strategy_id, target_number))
                    for target_number in target_numbers
                ]
                complete = [
                    row
                    for row in expected
                    if row is not None
                    and row["replay_status"] == "COMPLETE"
                    and row["actual_native_ticket_count"]
                    == descriptors_by_id[strategy_id]["native_ticket_count"]
                ]
                status_counts = Counter(
                    "MISSING" if row is None else cast(str, row["replay_status"])
                    for row in expected
                )
                eligible = len(complete) == len(target_numbers)
                strategy_coverage[window_name] = {
                    "eligible": eligible,
                    "observations": len(complete),
                    "observations_required": len(target_numbers),
                    "status_counts": dict(sorted(status_counts.items())),
                    "reason": None if eligible else "WINDOW_INELIGIBLE_INCOMPLETE_OBSERVATIONS",
                }
            category_coverage[strategy_id] = strategy_coverage

        for window_name, _size in WINDOWS:
            window = cast(Mapping[str, Any], manifest["target_windows"][window_name])
            target_numbers = tuple(cast(list[str], window["draw_numbers"]))
            metrics: list[dict[str, object]] = []
            for strategy_id in strategy_ids:
                descriptor = descriptors_by_id[strategy_id]
                complete_rows = [
                    rows_by_key[(strategy_id, target_number)]
                    for target_number in target_numbers
                    if (strategy_id, target_number) in rows_by_key
                    and rows_by_key[(strategy_id, target_number)]["replay_status"] == "COMPLETE"
                    and rows_by_key[(strategy_id, target_number)]["actual_native_ticket_count"]
                    == descriptor["native_ticket_count"]
                ]
                if len(complete_rows) == len(target_numbers):
                    metrics.append(
                        _metric_row(
                            descriptor,
                            complete_rows,
                            first_target=cast(str, window["first_target"]),
                            last_target=cast(str, window["last_target"]),
                            observations_required=len(target_numbers),
                        )
                    )
            metrics.sort(
                key=lambda metric: (
                    -float(cast(str, metric["official_any_prize_rate"])),
                    -cast(int, metric["successful_draws"]),
                    cast(str, metric["strategy_id"]),
                )
            )
            for rank, metric in enumerate(metrics, start=1):
                metric["rank"] = rank
            category_windows[window_name] = {
                "status": "COMPLETE" if len(metrics) >= 5 else "TOP5_INCOMPLETE",
                "eligible_count": len(metrics),
                "top5": metrics[:5] if len(metrics) >= 5 else [],
                "eligible_rankings": metrics,
            }
        leaderboards[category] = category_windows
        coverage[category] = category_coverage

    cross_window: dict[str, object] = {}
    for category in category_ids:
        category_board = cast(Mapping[str, Any], leaderboards[category])
        top5_by_strategy: dict[str, list[str]] = defaultdict(list)
        first_by_strategy: dict[str, list[str]] = defaultdict(list)
        rank_by_window: dict[str, dict[str, int]] = {}
        for window_name, _size in WINDOWS:
            board = cast(Mapping[str, Any], category_board[window_name])
            for metric in cast(Sequence[Mapping[str, Any]], board["top5"]):
                top5_by_strategy[cast(str, metric["strategy_id"])].append(window_name)
            for metric in cast(Sequence[Mapping[str, Any]], board["eligible_rankings"]):
                rank_by_window.setdefault(cast(str, metric["strategy_id"]), {})[
                    window_name
                ] = cast(int, metric["rank"])
                if metric["rank"] == 1:
                    first_by_strategy[cast(str, metric["strategy_id"])].append(window_name)
        movements = [
            {
                "strategy_id": strategy_id,
                "rank_recent_50": ranks["RECENT_50"],
                "rank_recent_750": ranks["RECENT_750"],
                "absolute_movement": abs(ranks["RECENT_50"] - ranks["RECENT_750"]),
            }
            for strategy_id, ranks in rank_by_window.items()
            if "RECENT_50" in ranks and "RECENT_750" in ranks
        ]
        movements.sort(
            key=lambda item: (
                -cast(int, item["absolute_movement"]),
                cast(str, item["strategy_id"]),
            )
        )
        missing = {
            strategy_id: category_coverage
            for strategy_id, category_coverage in cast(
                Mapping[str, Any], coverage[category]
            ).items()
            if not all(
                cast(bool, cast(Mapping[str, Any], category_coverage)[window_name]["eligible"])
                for window_name, _size in WINDOWS
            )
        }
        cross_window[category] = {
            "top5_union": dict(sorted(top5_by_strategy.items())),
            "top5_common_to_all_windows": sorted(
                strategy_id
                for strategy_id, names in top5_by_strategy.items()
                if len(names) == len(WINDOWS)
            ),
            "number_one_in_multiple_windows": {
                strategy_id: names
                for strategy_id, names in sorted(first_by_strategy.items())
                if len(names) > 1
            },
            "strongest_long_window_performer": (
                cast(
                    Sequence[Mapping[str, Any]],
                    category_board["RECENT_750"]["eligible_rankings"],
                )[0]
                if cast(
                    Sequence[Mapping[str, Any]],
                    category_board["RECENT_750"]["eligible_rankings"],
                )
                else None
            ),
            "largest_short_vs_long_rank_movement": movements[0] if movements else None,
            "exact_native_strategies_lacking_full_coverage": sorted(missing),
        }

    return {
        "schema_version": RANKING_SCHEMA,
        "run_id": RUN_ID,
        "sealed_evidence_sha256": manifest["evidence"]["sha256"],
        "leaderboards": leaderboards,
        "coverage": coverage,
        "cross_window": cross_window,
        "ranking_contract": {
            "primary_metric": "OFFICIAL_ANY_PRIZE_RATE",
            "success_unit": "distinct_target_draw",
            "ticket_level_double_counting": False,
            "tie_break": [
                "OFFICIAL_ANY_PRIZE_RATE_DESC",
                "SUCCESSFUL_DRAWS_DESC",
                "STRATEGY_ID_ASC",
            ],
            "source": "sealed_target_evidence_reopened_read_only",
        },
    }


def rank_sealed_evidence(evidence_dir: Path) -> dict[str, object]:
    """Reopen a sealed evidence bundle and write a ranking projection."""

    manifest, rows, manifest_sha = _load_sealed_bundle(evidence_dir)
    ranking = _rank_from_rows(manifest, rows)
    ranking["sealed_manifest_sha256"] = manifest_sha
    _write_json(evidence_dir / RANKING_FILENAME, ranking)
    return ranking


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    replay = subparsers.add_parser("replay", help="execute and seal exact-native evidence")
    replay.add_argument("--output-dir", type=Path, required=True)
    rank = subparsers.add_parser("rank", help="rank only from a reopened sealed bundle")
    rank.add_argument("--evidence-dir", type=Path, required=True)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    try:
        if args.command == "replay":
            manifest = run_replay(args.output_dir)
            evidence = cast(Mapping[str, object], manifest["evidence"])
            print(
                json.dumps(
                    {
                        "status": "SEALED",
                        "evidence_sha256": evidence["sha256"],
                        "record_count": evidence["record_count"],
                        "output_dir": str(args.output_dir),
                    },
                    sort_keys=True,
                )
            )
        else:
            ranking = rank_sealed_evidence(args.evidence_dir)
            print(
                json.dumps(
                    {
                        "status": "RANKED_FROM_SEALED_EVIDENCE",
                        "sealed_manifest_sha256": ranking["sealed_manifest_sha256"],
                        "output": str(args.evidence_dir / RANKING_FILENAME),
                    },
                    sort_keys=True,
                )
            )
    except (ReplayTaskError, OSError, ValueError, sqlite3.DatabaseError) as exc:
        raise SystemExit(f"B649_EXACT_NATIVE_REPLAY_ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
