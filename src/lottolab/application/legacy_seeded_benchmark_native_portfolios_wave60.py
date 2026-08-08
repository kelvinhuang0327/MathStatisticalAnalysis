"""Frozen seeded Hybrid, Orthogonal, and Zone benchmark replay."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from functools import lru_cache
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Final, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

HYBRID_METHOD_ID = "tools/hybrid_integration_benchmark.py"
ORTHOGONAL_METHOD_ID = (
    "tools/orthogonal_diversification_benchmark.py"
)
ZONE_METHOD_ID = "tools/zone_split_optimizer.py"
SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS = (
    HYBRID_METHOD_ID,
    ORTHOGONAL_METHOD_ID,
    ZONE_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE60_METHOD: Final = MappingProxyType(
    {
        HYBRID_METHOD_ID: (
            "5789ca8854224383a3c84e62871bc891c0661699309ae32aeff65ca403b3a64b"
        ),
        ORTHOGONAL_METHOD_ID: (
            "ce068c676ca5b16e48d95499a8b9c4cc8ba105962b02c71ad9b076f68659ca71"
        ),
        ZONE_METHOD_ID: (
            "0bf85e3e151766d3bdc174f5395200e730d0c45233afad0d1d91d43200149fe3"
        ),
    }
)
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD: Final = (
    MappingProxyType(
        {
            HYBRID_METHOD_ID: 12,
            ORTHOGONAL_METHOD_ID: 35,
            ZONE_METHOD_ID: 18,
        }
    )
)
LOCAL_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD: Final = (
    MappingProxyType(
        {
            HYBRID_METHOD_ID: 4,
            ORTHOGONAL_METHOD_ID: 14,
            ZONE_METHOD_ID: 6,
        }
    )
)
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE60_METHOD: Final = (
    MappingProxyType(
        {
            HYBRID_METHOD_ID: (
                "TWELVE_POSITIONAL_TICKETS_FOUR_LOCAL_HYBRID_"
                "STRATEGIES_X_THREE_BETS_IN_DECLARATION_ORDER"
            ),
            ORTHOGONAL_METHOD_ID: (
                "THIRTY_FIVE_POSITIONAL_TICKETS_SEVEN_ORTHOGONAL_"
                "STRATEGIES_X_TWO_THEN_THREE_BETS_IN_DECLARATION_ORDER"
            ),
            ZONE_METHOD_ID: (
                "EIGHTEEN_POSITIONAL_TICKETS_SIX_ZONE_VARIANTS_X_"
                "THREE_BETS_IN_DECLARATION_ORDER"
            ),
        }
    )
)
IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE60_METHOD: Final = (
    MappingProxyType(
        {
            HYBRID_METHOD_ID: (
                "Prod Optimizer: imported MultiBetOptimizer",
            ),
            ORTHOGONAL_METHOD_ID: (),
            ZONE_METHOD_ID: (),
        }
    )
)

SOURCE_NATIVE_WAVE60_PROTOCOL = (
    "legacy_seeded_benchmark_native_wave60/v1"
)
CAUSAL_PROTOCOL = (
    "FROZEN_BIG_LOTTO_LOCAL_CONFIG_ORDER_TARGET_STABLE_SEED42_V1"
)
DEFAULT_SOURCE_NATIVE_WAVE60_USER_SEED = (
    "biglotto-full-universe-seeded-benchmarks-wave60-v1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
LEDGER_RESOURCE_NAME = (
    "biglotto_seeded_benchmarks_wave60_ticket_ledger_v1.json"
)
LEDGER_SCHEMA_VERSION = (
    "BIG_LOTTO_SEEDED_BENCHMARKS_WAVE60_TICKET_LEDGER_V1"
)
LEDGER_FILE_SHA256 = (
    "0834d1b9e1acb622a142fbf29b35ef2a4aa5d269583b67a0fecd6862ca9ccc4b"
)
LEDGER_CONTENT_SHA256 = (
    "5541db19ad9ffe08d43ea375415662b19063db40df28d58ae8a1dfe1ecc52ab6"
)
SOURCE_REFERENCE_RUNTIME = (
    "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_"
    "TARGET_STABLE_PYTHON_AND_NUMPY_SEED_42"
)
MODEL_CANDIDATE_K = 49
MINIMUM_HISTORY_DRAWS = 1
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"
CAUSAL_ELIGIBILITY_RULE = (
    "TARGET_USES_ONLY_THE_FULL_STRICTLY_EARLIER_DRAW_PREFIX"
)
INSUFFICIENT_HISTORY_REASON = "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF"


class LegacySeededBenchmarkNativeWave60Error(ValueError):
    """A wave-60 request or packaged ledger violates its contract."""


class LegacySeededBenchmarkNativeWave60SourceError(
    LegacySeededBenchmarkNativeWave60Error
):
    """The frozen source has no executable output for this target."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySeededBenchmarkNativeWave60Request:
    legacy_method_id: str
    target_draw_number: str
    target_draw_date: date
    history: tuple[LegacyHistoryDraw, ...]
    dataset_sha256: str
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE60_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySeededBenchmarkNativeWave60Metadata:
    protocol: str
    causal_protocol: str
    legacy_method_id: str
    source_sha256: str
    target_draw_number: str
    target_draw_date: str
    replicate_id: int
    user_seed: str | int
    seed_material: str
    seed_digest: str
    seed_integer: int
    random_protocol: str
    randomness_used: bool
    randomness_reproduction: str
    history_draw_count: int
    history_first_draw_number: str
    history_cutoff_draw_number: str
    source_history_order: str
    source_history_order_detail: str
    context_draw_count: int
    context_numbers_sha256: str
    minimum_history_draws: int
    source_candidate_k_values: tuple[int, ...]
    candidate_k: None
    native_ticket_count: int
    native_ticket_count_semantics: str
    native_ticket_order: str
    native_duplicate_ticket_count: int
    combination_count: None
    local_configuration_count: int
    imported_comparators_excluded: tuple[str, ...]
    causal_eligibility_rule: str
    source_reference_runtime: str
    ledger_schema_version: str
    ledger_file_sha256: str
    ledger_content_sha256: str
    ledger_target_index: int

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySeededBenchmarkNativeWave60Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySeededBenchmarkNativeWave60Metadata


@dataclass(frozen=True, slots=True)
class _Ledger:
    targets: tuple[str, ...]
    target_index: MappingProxyType[str, int]
    context_sha256: tuple[str, ...]
    tickets_by_method: MappingProxyType[
        str, tuple[tuple[Ticket, ...] | None, ...]
    ]
    closed_reason_by_method: MappingProxyType[
        str, tuple[str | None, ...]
    ]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _ticket(value: object) -> Ticket:
    if not isinstance(value, list):
        raise LegacySeededBenchmarkNativeWave60Error(
            "packaged wave-60 ticket must be an array"
        )
    values = cast(list[object], value)
    if not all(type(number) is int for number in values):
        raise LegacySeededBenchmarkNativeWave60Error(
            "packaged wave-60 ticket must contain integers"
        )
    integers = cast(list[int], values)
    if (
        len(integers) != 6
        or integers != sorted(integers)
        or len(set(integers)) != 6
        or any(not 1 <= number <= 49 for number in integers)
    ):
        raise LegacySeededBenchmarkNativeWave60Error(
            "packaged wave-60 ticket is not a sorted legal ticket"
        )
    return cast(Ticket, tuple(integers))


@lru_cache(maxsize=1)
def _load_ledger() -> _Ledger:
    resource = files("lottolab.strategies.data").joinpath(
        LEDGER_RESOURCE_NAME
    )
    raw = resource.read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEDGER_FILE_SHA256:
        raise LegacySeededBenchmarkNativeWave60Error(
            "packaged wave-60 ledger file SHA changed"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacySeededBenchmarkNativeWave60Error(
            "packaged wave-60 ledger is invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise LegacySeededBenchmarkNativeWave60Error(
            "packaged wave-60 ledger must be an object"
        )
    document = cast(dict[str, Any], parsed)
    reduced = {
        key: value
        for key, value in document.items()
        if key != "ledger_content_sha256"
    }
    if (
        document.get("ledger_schema_version")
        != LEDGER_SCHEMA_VERSION
        or document.get("ledger_content_sha256")
        != LEDGER_CONTENT_SHA256
        or hashlib.sha256(_canonical_bytes(reduced)).hexdigest()
        != LEDGER_CONTENT_SHA256
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("frozen_source_commit")
        != FROZEN_SOURCE_COMMIT
        or document.get("causal_protocol") != CAUSAL_PROTOCOL
        or document.get("source_sha256_by_method")
        != dict(SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE60_METHOD)
        or document.get("native_ticket_count_by_method")
        != dict(NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD)
        or document.get("local_configuration_count_by_method")
        != dict(
            LOCAL_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD
        )
    ):
        raise LegacySeededBenchmarkNativeWave60Error(
            "packaged wave-60 ledger identity changed"
        )
    targets_raw = cast(list[object], document.get("targets", []))
    contexts_raw = cast(
        list[object],
        document.get("context_sha256", []),
    )
    if (
        len(targets_raw) != 2149
        or len(contexts_raw) != 2149
        or not all(isinstance(value, str) for value in targets_raw)
        or not all(
            isinstance(value, str) and len(value) == 64
            for value in contexts_raw
        )
    ):
        raise LegacySeededBenchmarkNativeWave60Error(
            "packaged wave-60 target index changed"
        )
    targets = cast(tuple[str, ...], tuple(targets_raw))
    contexts = cast(tuple[str, ...], tuple(contexts_raw))
    tickets_raw = cast(
        dict[str, list[object]],
        document.get("tickets_by_method", {}),
    )
    reasons_raw = cast(
        dict[str, list[object]],
        document.get("closed_reason_by_method", {}),
    )
    if (
        set(tickets_raw) != set(SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS)
        or set(reasons_raw)
        != set(SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS)
    ):
        raise LegacySeededBenchmarkNativeWave60Error(
            "packaged wave-60 method set changed"
        )
    tickets_by_method: dict[
        str, tuple[tuple[Ticket, ...] | None, ...]
    ] = {}
    closed_by_method: dict[str, tuple[str | None, ...]] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS:
        ticket_rows = tickets_raw[method_id]
        reason_rows = reasons_raw[method_id]
        if len(ticket_rows) != 2149 or len(reason_rows) != 2149:
            raise LegacySeededBenchmarkNativeWave60Error(
                f"packaged wave-60 coverage changed: {method_id}"
            )
        portfolios: list[tuple[Ticket, ...] | None] = []
        reasons: list[str | None] = []
        expected_count = (
            NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD[
                method_id
            ]
        )
        for ticket_row, reason in zip(
            ticket_rows,
            reason_rows,
            strict=True,
        ):
            if ticket_row is None:
                portfolios.append(None)
            elif isinstance(ticket_row, list):
                portfolio = tuple(
                    _ticket(ticket)
                    for ticket in cast(list[object], ticket_row)
                )
                if len(portfolio) != expected_count:
                    raise LegacySeededBenchmarkNativeWave60Error(
                        "packaged wave-60 native count changed"
                    )
                portfolios.append(portfolio)
            else:
                raise LegacySeededBenchmarkNativeWave60Error(
                    "packaged wave-60 portfolio is invalid"
                )
            if reason is not None and not isinstance(reason, str):
                raise LegacySeededBenchmarkNativeWave60Error(
                    "packaged wave-60 closed reason is invalid"
                )
            reasons.append(reason)
        tickets_by_method[method_id] = tuple(portfolios)
        closed_by_method[method_id] = tuple(reasons)
    return _Ledger(
        targets=targets,
        target_index=MappingProxyType(
            {
                target: index
                for index, target in enumerate(targets)
            }
        ),
        context_sha256=contexts,
        tickets_by_method=MappingProxyType(tickets_by_method),
        closed_reason_by_method=MappingProxyType(closed_by_method),
    )


def load_legacy_seeded_benchmark_native_wave60_ledger_for_verification() -> (
    _Ledger
):
    """Expose the immutable checksummed ledger to verification code."""

    return _load_ledger()


def _context_sha256(
    history: tuple[LegacyHistoryDraw, ...],
) -> str:
    return hashlib.sha256(
        json.dumps(
            [list(draw.numbers) for draw in history],
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def generate_legacy_seeded_benchmark_native_wave60_portfolio(
    request: LegacySeededBenchmarkNativeWave60Request,
) -> LegacySeededBenchmarkNativeWave60Result:
    """Replay one exact frozen-runtime positional benchmark portfolio."""

    if (
        request.legacy_method_id
        not in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS
        or type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.target_draw_date) is not date
        or type(request.dataset_sha256) is not str or not request.dataset_sha256
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
    ):
        raise LegacySeededBenchmarkNativeWave60Error(
            "invalid wave-60 request identity"
        )
    ledger = _load_ledger()
    target_index = ledger.target_index.get(request.target_draw_number)
    if target_index is None:
        raise LegacySeededBenchmarkNativeWave60SourceError(
            "TARGET_OUTSIDE_FROZEN_WAVE60_TICKET_LEDGER"
        )
    context_sha256 = _context_sha256(request.history)
    if context_sha256 != ledger.context_sha256[target_index]:
        raise LegacySeededBenchmarkNativeWave60SourceError(
            "FROZEN_WAVE60_FULL_PREFIX_CONTEXT_MISMATCH"
        )
    tickets = ledger.tickets_by_method[
        request.legacy_method_id
    ][target_index]
    if tickets is None:
        reason = ledger.closed_reason_by_method[
            request.legacy_method_id
        ][target_index]
        raise LegacySeededBenchmarkNativeWave60SourceError(
            reason or "FROZEN_WAVE60_CLOSED_WITHOUT_REASON"
        )
    if not request.history:
        raise LegacySeededBenchmarkNativeWave60Error(
            "executable wave-60 target must have prior history"
        )
    seed_material = (
        "random.seed(42);numpy.random.seed(42);"
        "flatten_BIG_LOTTO_local_configurations_in_source_order"
    )
    return LegacySeededBenchmarkNativeWave60Result(
        tickets=tickets,
        metadata=LegacySeededBenchmarkNativeWave60Metadata(
            protocol=SOURCE_NATIVE_WAVE60_PROTOCOL,
            causal_protocol=CAUSAL_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE60_METHOD[
                    request.legacy_method_id
                ]
            ),
            target_draw_number=request.target_draw_number,
            target_draw_date=request.target_draw_date.isoformat(),
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=hashlib.sha256(
                seed_material.encode("utf-8")
            ).hexdigest(),
            seed_integer=42,
            random_protocol=(
                "PYTHON_RANDOM_AND_NUMPY_RANDOM_RESET_TO_42_AT_EACH_"
                "TARGET_BEFORE_DECLARED_BIG_LOTTO_LOCAL_CONFIG_ORDER"
            ),
            randomness_used=True,
            randomness_reproduction=(
                "SOURCE_RUNTIME_LEDGER_EXACT_TICKET_REPLAY"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="RECENT_FIRST",
            source_history_order_detail=(
                "DATABASE_LOGICAL_OLDEST_FIRST_STRICT_PREFIX_REVERSED_"
                "TO_SOURCE_RECENT_FIRST_BEFORE_LOCAL_SELECTOR_CALLS"
            ),
            context_draw_count=len(request.history),
            context_numbers_sha256=context_sha256,
            minimum_history_draws=MINIMUM_HISTORY_DRAWS,
            source_candidate_k_values=(49,),
            candidate_k=None,
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE60_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_order=(
                "FROZEN_BIG_LOTTO_NUM_BETS_BLOCK_THEN_DECLARED_"
                "STRATEGY_THEN_POSITION_ORDER"
            ),
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            combination_count=None,
            local_configuration_count=(
                LOCAL_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD[
                    request.legacy_method_id
                ]
            ),
            imported_comparators_excluded=(
                IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE60_METHOD[
                    request.legacy_method_id
                ]
            ),
            causal_eligibility_rule=CAUSAL_ELIGIBILITY_RULE,
            source_reference_runtime=SOURCE_REFERENCE_RUNTIME,
            ledger_schema_version=LEDGER_SCHEMA_VERSION,
            ledger_file_sha256=LEDGER_FILE_SHA256,
            ledger_content_sha256=LEDGER_CONTENT_SHA256,
            ledger_target_index=target_index,
        ),
    )


__all__ = [
    "CAUSAL_ELIGIBILITY_RULE",
    "CAUSAL_PROTOCOL",
    "CONTEXT_POLICY",
    "DEFAULT_SOURCE_NATIVE_WAVE60_USER_SEED",
    "FROZEN_SOURCE_COMMIT",
    "HYBRID_METHOD_ID",
    "IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE60_METHOD",
    "INSUFFICIENT_HISTORY_REASON",
    "LEDGER_CONTENT_SHA256",
    "LEDGER_FILE_SHA256",
    "LEDGER_RESOURCE_NAME",
    "LEDGER_SCHEMA_VERSION",
    "LOCAL_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD",
    "MINIMUM_HISTORY_DRAWS",
    "MODEL_CANDIDATE_K",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE60_METHOD",
    "ORTHOGONAL_METHOD_ID",
    "PINNED_DATASET_SHA256",
    "SOURCE_NATIVE_WAVE60_PROTOCOL",
    "SOURCE_REFERENCE_RUNTIME",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE60_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS",
    "ZONE_METHOD_ID",
    "LegacySeededBenchmarkNativeWave60Error",
    "LegacySeededBenchmarkNativeWave60Metadata",
    "LegacySeededBenchmarkNativeWave60Request",
    "LegacySeededBenchmarkNativeWave60Result",
    "LegacySeededBenchmarkNativeWave60SourceError",
    "generate_legacy_seeded_benchmark_native_wave60_portfolio",
    "load_legacy_seeded_benchmark_native_wave60_ledger_for_verification",
]
