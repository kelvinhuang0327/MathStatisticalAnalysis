"""Target-bound deterministic RNG producer seam for the frozen fixed-13 cohort.

Ten of the thirteen ``NEXT_DRAW_R2_FIXED_13_COHORT_PROSPECTIVE_HYPOTHESIS_FREEZE_R1``
members already emit one legal BIG_LOTTO ticket deterministically from a
zero-argument constructor. The remaining three bind the process-global
unseeded ``random`` module by default, so a future target has no immutable
replay-stable ticket identity
(``BIGLOTTO_FIXED13_PROSPECTIVE_PRODUCER_REACHABILITY_R1``). This module
injects a fresh, call-local, target-bound ``random.Random`` instance into
exactly those three constructors and leaves the other ten's zero-argument
construction and exact behavior untouched.

This seam returns data only. It never persists a prediction, seal, or
eligibility record, and it never reads official outcomes or the database.
"""

from __future__ import annotations

import hashlib
import json
import platform
import random
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import ClassVar, cast

from lottolab.application.use_cases.generate_bet import instantiate_adapter
from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import BetAdapter, BetAdapterExecution, CausalDrawRow
from lottolab.strategies.catalog import UnknownStrategyError, production_catalog
from lottolab.strategies.executable_registry import ExecutableRegistry, NotExecutableError

RNG_POLICY_ID = "TARGET_BOUND_DETERMINISTIC_V1"
RNG_DOMAIN_TAG = "LOTTOLAB_FIXED13_PROSPECTIVE_RNG_V1"
RNG_SEED_DERIVATION_FORMULA = (
    "seed_bytes = SHA256(RNG_DOMAIN_TAG + US + PINNED_FREEZE_SHA256_HEX + US "
    '+ strategy_id + US + "BIG_LOTTO" + US + official_draw_identity); '
    "US = b'\\x1f'; seed_int = int.from_bytes(seed_bytes, 'big') (no truncation); "
    "rng = random.Random(seed_int)"
)

_UNIT_SEPARATOR = b"\x1f"
_PINNED_FREEZE_SHA256_HEX = "61beff4d35f7b0d10502fe0d1f36cc39e5a240128499061eac2599132019154b"
_LOTTERY_TYPE_TEXT = "BIG_LOTTO"

FIXED_13_COHORT_STRATEGY_IDS: tuple[str, ...] = (
    "biglotto_p0_2bet_bet1",
    "biglotto_wave2_neighbor_ad_graph_bridge_bet",
    "biglotto_wave2_neighbor_ad_graph_centrality_bet",
    "biglotto_wave2_neighbor_ad_graph_pagerank_bet",
    "biglotto_zone_split_3bet_bet1",
    "biglotto_zone_split_3bet_bet3",
    "legacy_biglotto__attention_replay_predictor__a811e2eb8215",
    "legacy_biglotto__backtest_biglotto_hot_stop_rebound__1794a8c507ae",
    "legacy_biglotto__cold_hunter_predict__9e89f2b41add",
    "legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6",
    "legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
    "legacy_biglotto__frontend_ml_genetic__3a4324bc2aa9",
    "legacy_biglotto__frontend_odd_even_balance_strategy__5b7f125437d0",
)

RNG_REQUIRED_STRATEGY_IDS: frozenset[str] = frozenset(
    {
        "legacy_biglotto__frontend_auto_optimize_strategy__a121d28125c6",
        "legacy_biglotto__frontend_ml_features__3a4324bc2aa9",
        "legacy_biglotto__frontend_ml_genetic__3a4324bc2aa9",
    }
)


class AdapterConstruction(StrEnum):
    RNG_INJECTED = "RNG_INJECTED"
    ZERO_ARG_DEFAULT = "ZERO_ARG_DEFAULT"


class Fixed13ProspectiveProducerError(RuntimeError):
    """Fail-closed base error; every subclass carries the PRE_OUTCOME_INELIGIBLE disposition."""

    disposition: ClassVar[str] = "PRE_OUTCOME_INELIGIBLE"


class UnknownFixed13StrategyError(Fixed13ProspectiveProducerError):
    """strategy_id is not one of the frozen fixed-13 cohort members."""


class InvalidOfficialDrawIdentityError(Fixed13ProspectiveProducerError):
    """official_draw_identity is missing, empty, or not an exact string."""


class FreezeIdentityMismatchError(Fixed13ProspectiveProducerError):
    """freeze_sha256_hex is malformed or does not match the pinned frozen hypothesis."""


class AdapterMetadataUnavailableError(Fixed13ProspectiveProducerError):
    """The canonical catalog/registry could not resolve this member's adapter class."""


class EmptyCausalHistoryError(Fixed13ProspectiveProducerError):
    """causal_history must contain at least one immutable prior draw row."""


@dataclass(frozen=True, slots=True)
class ProducerImplementationIdentity:
    repository_head: str
    repository_tree: str
    module_path: str

    def __post_init__(self) -> None:
        if type(self.repository_head) is not str or not self.repository_head:
            raise ValueError("repository_head must be a non-empty string")
        if type(self.repository_tree) is not str or not self.repository_tree:
            raise ValueError("repository_tree must be a non-empty string")
        if type(self.module_path) is not str or not self.module_path:
            raise ValueError("module_path must be a non-empty string")


@dataclass(frozen=True, slots=True)
class Fixed13ProspectiveProducerRecord:
    """One member's DATA-ONLY execution result plus its RNG/provenance seal.

    Never persisted by this module — see the module docstring.
    """

    strategy_id: str
    official_draw_identity: str
    execution: BetAdapterExecution
    rng_policy_id: str
    rng_domain_tag: str
    rng_seed_derivation_formula: str
    per_member_rng_required: bool
    per_member_rng_seed_sha256_hex: str | None
    per_member_adapter_path: str
    per_member_adapter_construction: AdapterConstruction
    per_member_causal_history_digest: str
    causal_history_row_count: int
    causal_history_last_draw_identity: str
    producer_implementation_identity: ProducerImplementationIdentity
    python_implementation_identity: str
    rng_selfcheck_vector: tuple[float, float, float] | None
    historical_r2_ticket_parity_note: str

    def __post_init__(self) -> None:
        rng_fields_present = (
            self.per_member_rng_seed_sha256_hex is not None
            and self.rng_selfcheck_vector is not None
        )
        if self.per_member_rng_required:
            if (
                not rng_fields_present
                or self.per_member_adapter_construction is not AdapterConstruction.RNG_INJECTED
            ):
                raise ValueError(
                    "RNG-required members must carry a seed, a selfcheck vector, "
                    "and RNG_INJECTED construction"
                )
        elif (
            rng_fields_present
            or self.per_member_adapter_construction is not AdapterConstruction.ZERO_ARG_DEFAULT
        ):
            raise ValueError(
                "zero-arg members must not carry an RNG seed/selfcheck vector "
                "and must record ZERO_ARG_DEFAULT construction"
            )


def _require_known_cohort_member(strategy_id: object) -> str:
    if type(strategy_id) is not str or strategy_id not in FIXED_13_COHORT_STRATEGY_IDS:
        raise UnknownFixed13StrategyError(
            f"{strategy_id!r} is not a frozen fixed-13 cohort strategy_id"
        )
    return strategy_id


def _require_official_draw_identity(value: object) -> str:
    if type(value) is not str or not value:
        raise InvalidOfficialDrawIdentityError(
            "official_draw_identity must be a non-empty exact string"
        )
    return value


def _require_matching_freeze_identity(freeze_sha256_hex: object) -> str:
    is_well_formed_hex = (
        type(freeze_sha256_hex) is str
        and len(freeze_sha256_hex) == 64
        and freeze_sha256_hex == freeze_sha256_hex.lower()
        and all(char in "0123456789abcdef" for char in freeze_sha256_hex)
    )
    if not is_well_formed_hex:
        raise FreezeIdentityMismatchError(
            "freeze_sha256_hex must be a lowercase 64-character hex SHA-256 digest"
        )
    resolved = cast(str, freeze_sha256_hex)
    if resolved != _PINNED_FREEZE_SHA256_HEX:
        raise FreezeIdentityMismatchError(
            "freeze_sha256_hex does not match the pinned "
            "NEXT_DRAW_R2_FIXED_13_COHORT_PROSPECTIVE_HYPOTHESIS_FREEZE_R1 authority"
        )
    return resolved


def _require_nonempty_causal_history(causal_history: object) -> tuple[CausalDrawRow, ...]:
    is_valid = type(causal_history) is tuple and len(cast(tuple[object, ...], causal_history)) > 0
    if is_valid:
        is_valid = all(
            type(row) is CausalDrawRow for row in cast(tuple[object, ...], causal_history)
        )
    if not is_valid:
        raise EmptyCausalHistoryError("causal_history must be a non-empty tuple of CausalDrawRow")
    return cast(tuple[CausalDrawRow, ...], causal_history)


def _resolve_adapter_class(strategy_id: str) -> type[BetAdapter]:
    try:
        registry = ExecutableRegistry(production_catalog())
        adapter_class = registry.load_adapter(strategy_id)
    except (UnknownStrategyError, NotExecutableError) as exc:
        raise AdapterMetadataUnavailableError(
            f"{strategy_id}: no executable canonical adapter metadata"
        ) from exc
    if not (isinstance(adapter_class, type) and issubclass(adapter_class, BetAdapter)):
        raise AdapterMetadataUnavailableError(
            f"{strategy_id}: adapter_path does not resolve to a BetAdapter subclass"
        )
    return adapter_class


def _derive_target_bound_seed_bytes(*, strategy_id: str, official_draw_identity: str) -> bytes:
    """Implement the frozen TARGET_BOUND_DETERMINISTIC_V1 seed formula exactly.

    Deliberately excludes draw date, scheduled draw time, causal-history
    digest, history row count, outcome, wall clock, PID, host, run index, and
    retry counter — only strategy_id, official_draw_identity, and the pinned
    freeze/domain identity bind the seed.
    """

    payload = _UNIT_SEPARATOR.join(
        (
            RNG_DOMAIN_TAG.encode("utf-8"),
            _PINNED_FREEZE_SHA256_HEX.encode("utf-8"),
            strategy_id.encode("utf-8"),
            _LOTTERY_TYPE_TEXT.encode("utf-8"),
            official_draw_identity.encode("utf-8"),
        )
    )
    return hashlib.sha256(payload).digest()


def _causal_history_digest(causal_history: tuple[CausalDrawRow, ...]) -> str:
    encoded = json.dumps(
        [
            {"draw": row.draw, "date": row.date, "numbers": list(row.numbers)}
            for row in causal_history
        ],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _resolve_producer_implementation_identity() -> ProducerImplementationIdentity:
    repo_root = Path(__file__).resolve().parents[3]
    return ProducerImplementationIdentity(
        repository_head=_run_git(repo_root, "rev-parse", "HEAD"),
        repository_tree=_run_git(repo_root, "rev-parse", "HEAD^{tree}"),
        module_path=__name__,
    )


def _python_implementation_identity() -> str:
    return f"{platform.python_implementation()} {platform.python_version()}"


def _instantiate_rng_injected(adapter_class: type[BetAdapter], rng: random.Random) -> BetAdapter:
    adapter_factory = cast(Callable[..., BetAdapter], adapter_class)
    return adapter_factory(rng=rng)


def produce_fixed13_member(
    *,
    strategy_id: str,
    official_draw_identity: str,
    freeze_sha256_hex: str,
    causal_history: tuple[CausalDrawRow, ...],
) -> Fixed13ProspectiveProducerRecord:
    """Produce one frozen fixed-13 member's ticket plus its RNG/provenance seal.

    Exactly the three :data:`RNG_REQUIRED_STRATEGY_IDS` receive a fresh,
    target-bound ``random.Random`` built only from ``strategy_id``,
    ``official_draw_identity``, and the pinned freeze/domain identity. The
    other ten construct through the existing zero-argument production path
    (:func:`lottolab.application.use_cases.generate_bet.instantiate_adapter`)
    unchanged. Every input is validated fail-closed before any adapter is
    constructed — none of the checks below ever falls back to the
    process-global ``random`` module.
    """

    resolved_strategy_id = _require_known_cohort_member(strategy_id)
    resolved_draw_identity = _require_official_draw_identity(official_draw_identity)
    _require_matching_freeze_identity(freeze_sha256_hex)
    resolved_history = _require_nonempty_causal_history(causal_history)
    adapter_class = _resolve_adapter_class(resolved_strategy_id)

    rng_required = resolved_strategy_id in RNG_REQUIRED_STRATEGY_IDS
    seed_sha256_hex: str | None = None
    selfcheck_vector: tuple[float, float, float] | None = None

    if rng_required:
        seed_bytes = _derive_target_bound_seed_bytes(
            strategy_id=resolved_strategy_id,
            official_draw_identity=resolved_draw_identity,
        )
        seed_sha256_hex = seed_bytes.hex()
        seed_int = int.from_bytes(seed_bytes, "big")

        # Selfcheck derives from a Random(seed_int) that is never touched
        # again; the producer below always gets its own pristine instance.
        selfcheck_rng = random.Random(seed_int)
        selfcheck_vector = (
            selfcheck_rng.random(),
            selfcheck_rng.random(),
            selfcheck_rng.random(),
        )

        producer_rng = random.Random(seed_int)
        adapter = _instantiate_rng_injected(adapter_class, producer_rng)
        construction = AdapterConstruction.RNG_INJECTED
        parity_note = "NOT_ASSERTED_FOR_THE_THREE_MEMBERS"
    else:
        adapter = instantiate_adapter(resolved_strategy_id, adapter_class)
        construction = AdapterConstruction.ZERO_ARG_DEFAULT
        parity_note = "NOT_APPLICABLE_ZERO_ARG_MEMBER"

    execution = adapter.get_one_bet_with_emission(resolved_history, LotteryType.BIG_LOTTO)

    return Fixed13ProspectiveProducerRecord(
        strategy_id=resolved_strategy_id,
        official_draw_identity=resolved_draw_identity,
        execution=execution,
        rng_policy_id=RNG_POLICY_ID,
        rng_domain_tag=RNG_DOMAIN_TAG,
        rng_seed_derivation_formula=RNG_SEED_DERIVATION_FORMULA,
        per_member_rng_required=rng_required,
        per_member_rng_seed_sha256_hex=seed_sha256_hex,
        per_member_adapter_path=f"{adapter_class.__module__}:{adapter_class.__qualname__}",
        per_member_adapter_construction=construction,
        per_member_causal_history_digest=_causal_history_digest(resolved_history),
        causal_history_row_count=len(resolved_history),
        causal_history_last_draw_identity=resolved_history[-1].draw,
        producer_implementation_identity=_resolve_producer_implementation_identity(),
        python_implementation_identity=_python_implementation_identity(),
        rng_selfcheck_vector=selfcheck_vector,
        historical_r2_ticket_parity_note=parity_note,
    )


__all__ = [
    "FIXED_13_COHORT_STRATEGY_IDS",
    "RNG_DOMAIN_TAG",
    "RNG_POLICY_ID",
    "RNG_REQUIRED_STRATEGY_IDS",
    "RNG_SEED_DERIVATION_FORMULA",
    "AdapterConstruction",
    "AdapterMetadataUnavailableError",
    "EmptyCausalHistoryError",
    "Fixed13ProspectiveProducerError",
    "Fixed13ProspectiveProducerRecord",
    "FreezeIdentityMismatchError",
    "InvalidOfficialDrawIdentityError",
    "ProducerImplementationIdentity",
    "UnknownFixed13StrategyError",
    "produce_fixed13_member",
]
