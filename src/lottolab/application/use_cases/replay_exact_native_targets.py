"""Use case: replay the exact-native BIG_LOTTO universe over one explicit
contiguous target-index range.

Canonicalizes the donor exact-native replay engine
(``tools/b649_exact_native_replay.py`` at commit ``85d2b4578d437b66bd015c60dd1f9bdc8404e755``)
and the POST-PR231 sharded orchestrator/worker pair into tracked source: no
``sys.path`` injection from another worktree, no path graft onto
``lottolab.infrastructure.persistence``, and no dependency on
``storage_authorities.py`` (unpublished relative to ``origin/main`` -- see
:func:`load_authoritative_draws`). Every donor task-specific constant
(``RUN_ID``, ``MAX_VISIBLE_DRAW``, expected draw identity, native ticket
counts, window contract) is an explicit input here, not a hard-coded
executable constant; current defaults reproduce current behavior exactly.

This module intentionally does not import ``_apply_runtime_optimizations``
(the donor's Evolution-Engine-caching monkeypatch): the exact-native
universe (fixed ``native_ticket_count_bounds``) structurally excludes
Evolution Engine's ranged ``(1, 10)`` bounds for every current binding, so
the monkeypatch's target symbols are never reached by this module.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import sqlite3
import subprocess
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol, cast

from lottolab.application.legacy_source_native_portfolios_wave26 import (
    DEFAULT_SOURCE_NATIVE_WAVE26_USER_SEED,
    SOURCE_NATIVE_WAVE26_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE26_METHOD,
)
from lottolab.application.use_cases.generate_bet import instantiate_portfolio_adapter
from lottolab.domain.draws import LotteryType
from lottolab.domain.exact_native_replay import (
    DEFAULT_NATIVE_TICKET_COUNTS,
    DEFAULT_WINDOW_ORDER,
    DEFAULT_WINDOW_SIZES,
    Draw,
    ExactNativeReplayError,
    RuntimeBinding,
    assert_causal_history,
    exact_native_descriptors,
    freeze_visible_draws,
    window_names_for_target,
)
from lottolab.domain.exact_native_replay import target_windows as compute_target_windows
from lottolab.domain.lottery_rules import BIG_LOTTO_RULE_CONTRACT
from lottolab.domain.prize_evaluation import evaluate_lottery_prize
from lottolab.domain.strategies import StrategyDescriptor
from lottolab.evidence.exact_native_replay_manifest import (
    EVIDENCE_SCHEMA,
    build_catalog_universe_payload,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from lottolab.evidence.exact_native_replay_manifest import history_fingerprint as _fingerprint
from lottolab.strategies.adapters.base import (
    BetAdapterExecution,
    CausalDrawRow,
    InsufficientHistory,
    InvalidOutput,
)
from lottolab.strategies.catalog import production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry

DEFAULT_MAX_VISIBLE_DRAW = "115000083"
DEFAULT_EXPECTED_MAIN_NUMBERS: tuple[int, ...] = (9, 20, 23, 26, 36, 44)
DEFAULT_EXPECTED_SPECIAL_NUMBER = 4

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


class ExactNativeReplayRuntimeError(ExactNativeReplayError):
    """A runtime (adapter loading, draw-authority, or source-identity) failure."""


class _PortfolioRuntime(Protocol):
    def get_bets_with_emission(
        self, history: object, lottery_type: LotteryType
    ) -> tuple[BetAdapterExecution, ...]: ...


def causal_row(draw: Draw) -> CausalDrawRow:
    """Narrow one domain :class:`Draw` to the strategy adapter's causal-row shape."""

    return CausalDrawRow(
        draw=draw.draw_number, date=draw.draw_date.isoformat(), numbers=draw.main_numbers
    )


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(("git", *args), cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def source_freeze(repo: Path) -> dict[str, str]:
    """Mechanically derive producer/source identity from the tracked runtime tree.

    Replaces the donor's hard-coded ``producer_sha256`` literal: identity is
    always this actually-running tree's branch/HEAD/tree, verified clean --
    never a copied, stale SHA.
    """

    status = _git(repo, "status", "--porcelain=v1", "-uall")
    if status:
        raise ExactNativeReplayRuntimeError(
            "REPLAY_SOURCE_WORKTREE_NOT_CLEAN: " + status.replace("\n", " | ")
        )
    return {
        "branch": _git(repo, "branch", "--show-current"),
        "head": _git(repo, "rev-parse", "HEAD"),
        "tree": _git(repo, "rev-parse", "HEAD^{tree}"),
        "status": "clean",
    }


def _parse_numbers(raw: object, *, field_name: str) -> tuple[int, ...]:
    if type(raw) is not list:
        raise ExactNativeReplayRuntimeError(f"DRAW_AUTHORITY_INVALID_{field_name}")
    raw_values = cast(list[object], raw)
    if not all(type(value) is int for value in raw_values):
        raise ExactNativeReplayRuntimeError(f"DRAW_AUTHORITY_INVALID_{field_name}")
    numbers = tuple(cast(list[int], raw_values))
    if len(numbers) != BIG_LOTTO_RULE_CONTRACT.main_number_count:
        raise ExactNativeReplayRuntimeError(f"DRAW_AUTHORITY_INVALID_{field_name}_COUNT")
    if numbers != tuple(sorted(numbers)) or len(set(numbers)) != len(numbers):
        raise ExactNativeReplayRuntimeError(f"DRAW_AUTHORITY_INVALID_{field_name}_ORDER")
    if any(
        number < BIG_LOTTO_RULE_CONTRACT.main_number_min
        or number > BIG_LOTTO_RULE_CONTRACT.main_number_max
        for number in numbers
    ):
        raise ExactNativeReplayRuntimeError(f"DRAW_AUTHORITY_INVALID_{field_name}_RANGE")
    return numbers


def load_authoritative_draws(
    draw_authority_db: Path,
) -> tuple[tuple[Draw, ...], dict[str, object]]:
    """Read-only load of every BIG_LOTTO draw from an explicit, caller-verified DB path.

    Takes the path as an explicit input rather than resolving it through
    ``StorageAuthorityRegistry``: that class is unpublished relative to
    ``origin/main`` (present only on local ``main``, never merged) -- porting
    it would import from source this migration cannot branch from. This
    keeps the donor's essential safety property -- read-only open plus a
    before/after SHA-256 equality guard -- without the registry/verification
    apparatus around it.
    """

    if not draw_authority_db.is_file():
        raise ExactNativeReplayRuntimeError(f"DRAW_AUTHORITY_DB_NOT_FOUND: {draw_authority_db}")
    before_sha = sha256_file(draw_authority_db)
    try:
        with sqlite3.connect(f"file:{draw_authority_db}?mode=ro", uri=True) as connection:
            connection.execute("PRAGMA query_only=ON")
            rows = connection.execute(
                "SELECT draw_number, draw_date, main_numbers_json, "
                "special_numbers_json FROM draws WHERE lottery_type = ? "
                "ORDER BY draw_date, CAST(draw_number AS INTEGER), draw_number",
                (LotteryType.BIG_LOTTO.value,),
            ).fetchall()
    except (OSError, sqlite3.DatabaseError) as exc:
        raise ExactNativeReplayRuntimeError(
            "DRAW_AUTHORITY_BLOCKED: read-only query failed"
        ) from exc
    after_sha = sha256_file(draw_authority_db)
    if before_sha != after_sha:
        raise ExactNativeReplayRuntimeError("DRAW_AUTHORITY_BLOCKED: authority changed during read")

    draws: list[Draw] = []
    for row in rows:
        if len(row) != 4 or type(row[0]) is not str or type(row[1]) is not str:
            raise ExactNativeReplayRuntimeError("DRAW_AUTHORITY_INVALID_ROW_SHAPE")
        try:
            draw_date = date.fromisoformat(row[1])
            raw_main = json.loads(row[2])
            raw_special = json.loads(row[3])
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ExactNativeReplayRuntimeError("DRAW_AUTHORITY_INVALID_ROW_JSON") from exc
        main_numbers = _parse_numbers(raw_main, field_name="MAIN_NUMBERS")
        if type(raw_special) is not list:
            raise ExactNativeReplayRuntimeError("DRAW_AUTHORITY_INVALID_SPECIAL_NUMBER")
        special_values = cast(list[object], raw_special)
        if (
            len(special_values) != 1
            or type(special_values[0]) is not int
            or not 1 <= special_values[0] <= 49
            or special_values[0] in main_numbers
        ):
            raise ExactNativeReplayRuntimeError("DRAW_AUTHORITY_INVALID_SPECIAL_NUMBER")
        draws.append(
            Draw(
                draw_number=row[0],
                draw_date=draw_date,
                main_numbers=main_numbers,
                special_number=special_values[0],
            )
        )

    if not draws or tuple(sorted(draws, key=lambda draw: draw.sort_key)) != tuple(draws):
        raise ExactNativeReplayRuntimeError("DRAW_AUTHORITY_NOT_CHRONOLOGICAL")

    draw_payload = [
        {
            "draw_date": draw.draw_date.isoformat(),
            "draw_number": draw.draw_number,
            "main_numbers": list(draw.main_numbers),
            "special_number": draw.special_number,
        }
        for draw in draws
    ]
    metadata: dict[str, object] = {
        "capability": "DRAW_DATA",
        "schema": "DRAW_DATA_V3",
        "verification": {
            "exists": True,
            "query_only": True,
            "readable": True,
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
        "draw_payload_sha256": sha256_bytes(canonical_json_bytes(draw_payload)),
    }
    return tuple(draws), metadata


def catalog_freeze(
    *, native_ticket_counts: Sequence[int] = DEFAULT_NATIVE_TICKET_COUNTS
) -> tuple[tuple[StrategyDescriptor, ...], dict[str, object]]:
    """Freeze the current exact-native strategy universe and its provenance payload."""

    catalog = production_catalog()
    biglotto = tuple(catalog.list(lottery_type=LotteryType.BIG_LOTTO))
    exact = exact_native_descriptors(biglotto, native_ticket_counts=native_ticket_counts)
    exact_by_count = {
        count: tuple(descriptor for descriptor in exact if descriptor.native_ticket_count == count)
        for count in native_ticket_counts
    }
    universe = build_catalog_universe_payload(
        production_catalog_count=len(tuple(catalog)),
        all_biglotto_descriptors=biglotto,
        exact_native_by_count=exact_by_count,
    )
    return exact, universe


def _short_exception(exc: Exception) -> str:
    return str(exc).replace("\n", " ").strip()


def runtime_bindings(descriptors: Sequence[StrategyDescriptor]) -> tuple[RuntimeBinding, ...]:
    """Load and identity-verify one adapter per descriptor; never raises per-binding."""

    catalog = production_catalog()
    registry = ExecutableRegistry(catalog)
    bindings: list[RuntimeBinding] = []
    for descriptor in descriptors:
        try:
            adapter_class = registry.load_adapter(descriptor.strategy_id)
            implementation = instantiate_portfolio_adapter(descriptor.strategy_id, adapter_class)
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
                raise ExactNativeReplayRuntimeError("ADAPTER_IDENTITY_MISMATCH")
            if (
                getattr(implementation, "native_ticket_count", None)
                != descriptor.native_ticket_count
                or actual_bounds != descriptor.native_ticket_count_bounds
            ):
                raise ExactNativeReplayRuntimeError("ADAPTER_NATIVE_TICKET_COUNT_MISMATCH")
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


# --- Seed-metadata provenance (ported verbatim from the donor engine) ------

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


def seed_metadata(
    descriptor: StrategyDescriptor,
    history: tuple[CausalDrawRow, ...],
) -> dict[str, object]:
    """Recover the native adapter's own seed/state rule as evidence-row provenance.

    Read-only introspection of each adapter module's frozen seed material --
    never edits or monkeypatches adapter internals.
    """

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
        descriptor.strategy_id == "legacy_biglotto__constraint_filter_predictor__3a85b3995002"
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
                    "legacy NumPy RandomState(seed % 2**32) + random.Random(seed, version=2)"
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
                    "wave26 frozen statistical calls reseed from causal history length"
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
                    "random.Random(len(causal_history)) inside frozen statistical predictor"
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
                    "local random.Random(42) per adapter call; NumPy seed is output-inert"
                ),
                "configuration": "DIVERSIFIED_ENSEMBLE_V6_FIXED_SEED",
                "prestate_dependency": "causal_history_only",
            }
        )
    return metadata


# --- Row assembly and cell execution ---------------------------------------


def _base_evidence_row(
    run_id: str,
    descriptor: StrategyDescriptor,
    target: Draw,
    history: tuple[Draw, ...],
    windows: Mapping[str, Mapping[str, object]],
    seed: Mapping[str, object],
    *,
    history_fingerprint: str,
) -> dict[str, object]:
    cutoff = history[-1] if history else None
    return {
        "schema_version": EVIDENCE_SCHEMA,
        "run_id": run_id,
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
        "causal_history_fingerprint": history_fingerprint,
        "target_outcome_excluded": target not in history,
        "window_names": window_names_for_target(target, windows),
        "seed_metadata": dict(seed),
    }


def _failure_row(base: dict[str, object], *, status: str, reason: str) -> dict[str, object]:
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
    winners = [value for value in evaluations if cast(bool, value["is_winner"])]
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


def replay_cell(
    binding: RuntimeBinding,
    target: Draw,
    history: tuple[Draw, ...],
    windows: Mapping[str, Mapping[str, object]],
    run_id: str,
    *,
    causal_rows: tuple[CausalDrawRow, ...],
    history_fingerprint: str,
) -> dict[str, object]:
    """Execute one (strategy, target) cell and return its typed evidence row."""

    seed = seed_metadata(binding.descriptor, causal_rows)
    base = _base_evidence_row(
        run_id,
        binding.descriptor,
        target,
        history,
        windows,
        seed,
        history_fingerprint=history_fingerprint,
    )
    if binding.binding_error is not None:
        return _failure_row(
            base, status="EXECUTION_FAILURE", reason=f"BINDING_FAILURE: {binding.binding_error}"
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


# --- Single contiguous target-range orchestration ---------------------------


@dataclass(frozen=True, slots=True)
class ReplayTargetRangeRequest:
    run_id: str
    draw_authority_db: Path
    repository_root: Path
    output_path: Path
    start_index: int
    end_index: int
    native_ticket_counts: tuple[int, ...] = DEFAULT_NATIVE_TICKET_COUNTS
    max_visible_draw: str = DEFAULT_MAX_VISIBLE_DRAW
    expected_main_numbers: tuple[int, ...] | None = DEFAULT_EXPECTED_MAIN_NUMBERS
    expected_special_number: int | None = DEFAULT_EXPECTED_SPECIAL_NUMBER
    window_order: tuple[str, ...] = DEFAULT_WINDOW_ORDER
    window_sizes: Mapping[str, int | None] = field(
        default_factory=lambda: dict(DEFAULT_WINDOW_SIZES)
    )


@dataclass(frozen=True, slots=True)
class ReplayTargetRangeResult:
    actual_rows: int
    expected_rows: int
    binding_count: int
    status_counts: Mapping[str, int]
    evidence_sha256: str
    evidence_byte_size: int
    source: Mapping[str, object]
    catalog_universe: Mapping[str, object]
    draw_authority: Mapping[str, object]
    target_windows: Mapping[str, object]
    total_target_count: int
    first_target_draw: str | None
    last_target_draw: str | None
    later_draws_present_in_authority: bool


def replay_exact_native_target_range(
    request: ReplayTargetRangeRequest,
) -> ReplayTargetRangeResult:
    """Replay every current exact-native binding over ``[start_index, end_index)``.

    Resumable: if ``output_path`` already holds complete target-groups (a
    multiple of the current binding count), execution continues after them
    rather than re-computing already-sealed rows.
    """

    source = source_freeze(request.repository_root)
    descriptors, catalog_universe = catalog_freeze(
        native_ticket_counts=request.native_ticket_counts
    )
    loaded_draws, draw_authority = load_authoritative_draws(request.draw_authority_db)
    all_draws = freeze_visible_draws(
        loaded_draws,
        max_visible_draw=request.max_visible_draw,
        expected_main_numbers=request.expected_main_numbers,
        expected_special_number=request.expected_special_number,
    )
    later_present = any(
        int(draw.draw_number) > int(request.max_visible_draw) for draw in loaded_draws
    )
    windows = compute_target_windows(
        all_draws, window_order=request.window_order, window_sizes=request.window_sizes
    )
    bindings = runtime_bindings(descriptors) if descriptors else ()
    binding_count = len(bindings)

    total_targets = len(all_draws)
    start_i, end_i = request.start_index, request.end_index
    if not (0 <= start_i <= end_i <= total_targets):
        raise ExactNativeReplayRuntimeError(
            f"Invalid target range: [{start_i}, {end_i}) for total {total_targets}"
        )

    expected_rows = (end_i - start_i) * binding_count
    first_target_draw = all_draws[start_i].draw_number if start_i < end_i else None
    last_target_draw = all_draws[end_i - 1].draw_number if start_i < end_i else None

    request.output_path.parent.mkdir(parents=True, exist_ok=True)

    actual_rows = 0
    status_counts: Counter[str] = Counter()
    resume_index = start_i
    if (
        request.output_path.exists()
        and request.output_path.stat().st_size > 0
        and binding_count > 0
    ):
        existing_lines = [
            line
            for line in request.output_path.read_text(encoding="utf-8").strip().split("\n")
            if line
        ]
        completed_targets = len(existing_lines) // binding_count
        retained_rows = completed_targets * binding_count
        retained_lines = existing_lines[:retained_rows]
        request.output_path.write_text(
            "\n".join(retained_lines) + ("\n" if retained_lines else ""), encoding="utf-8"
        )
        actual_rows = retained_rows
        for line in retained_lines:
            row = json.loads(line)
            status_counts[row["replay_status"]] += 1
        resume_index = start_i + completed_targets

    with request.output_path.open("a", encoding="utf-8", newline="\n") as handle:
        for target_index in range(resume_index, end_i):
            target = all_draws[target_index]
            history = all_draws[:target_index]
            assert_causal_history(target, history)
            causal_rows = tuple(causal_row(draw) for draw in history)
            fingerprint = _fingerprint(history)
            for binding in bindings:
                row = replay_cell(
                    binding,
                    target,
                    history,
                    windows,
                    request.run_id,
                    causal_rows=causal_rows,
                    history_fingerprint=fingerprint,
                )
                handle.write(canonical_json_bytes(row).decode("utf-8"))
                actual_rows += 1
                status_counts[cast(str, row["replay_status"])] += 1

    if actual_rows != expected_rows:
        raise ExactNativeReplayRuntimeError(
            f"row count mismatch: expected {expected_rows}, got {actual_rows}"
        )

    evidence_sha256 = sha256_file(request.output_path)
    evidence_byte_size = request.output_path.stat().st_size

    return ReplayTargetRangeResult(
        actual_rows=actual_rows,
        expected_rows=expected_rows,
        binding_count=binding_count,
        status_counts=dict(sorted(status_counts.items())),
        evidence_sha256=evidence_sha256,
        evidence_byte_size=evidence_byte_size,
        source=source,
        catalog_universe=catalog_universe,
        draw_authority=draw_authority,
        target_windows=windows,
        total_target_count=total_targets,
        first_target_draw=first_target_draw,
        last_target_draw=last_target_draw,
        later_draws_present_in_authority=later_present,
    )


__all__ = [
    "DEFAULT_EXPECTED_MAIN_NUMBERS",
    "DEFAULT_EXPECTED_SPECIAL_NUMBER",
    "DEFAULT_MAX_VISIBLE_DRAW",
    "ExactNativeReplayRuntimeError",
    "ReplayTargetRangeRequest",
    "ReplayTargetRangeResult",
    "catalog_freeze",
    "causal_row",
    "load_authoritative_draws",
    "replay_cell",
    "replay_exact_native_target_range",
    "runtime_bindings",
    "seed_metadata",
    "source_freeze",
]
