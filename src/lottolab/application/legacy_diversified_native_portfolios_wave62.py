"""Frozen diversified ensemble and horizon replay for wave 62."""

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

ENSEMBLE_METHOD_ID = "tools/biglotto_diversified_ensemble.py"
BACKTEST_METHOD_ID = "tools/backtest_diversified_3bet.py"
SUPPORTED_METHODS = (ENSEMBLE_METHOD_ID, BACKTEST_METHOD_ID)
SOURCE_SHA256_BY_METHOD: Final = MappingProxyType(
    {
        ENSEMBLE_METHOD_ID: (
            "36dbfc14b360d0961b429e7e7a424340c9e81d20886e4d9814b5306c82e9ee7f"
        ),
        BACKTEST_METHOD_ID: (
            "03acff1d1bf7f6375b011bd3c6d5750cf4c58569396fb80e85c4820f243c6c17"
        ),
    }
)
NATIVE_TICKET_SEMANTICS_BY_METHOD: Final = MappingProxyType(
    {
        ENSEMBLE_METHOD_ID: (
            "SOURCE_DEFAULT_SEED42_THREE_POSITIONAL_TICKETS_"
            "CONSENSUS_PRIME_GNN_STRUCTURAL_FLUX_THEN_ENTROPY_OUTLIER"
        ),
        BACKTEST_METHOD_ID: (
            "SOURCE_MAIN_DIVERSIFIED_H150_THEN_H500_THREE_BET_"
            "BLOCKS_FLATTENED_TO_3_OR_6_POSITIONAL_TICKETS"
        ),
    }
)
NATIVE_TICKET_ORDER_BY_METHOD: Final = MappingProxyType(
    {
        ENSEMBLE_METHOD_ID: (
            "SOURCE_BET1_BET2_BET3_ORDER_BEFORE_ORDERED20"
        ),
        BACKTEST_METHOD_ID: (
            "SOURCE_HORIZON_150_THEN_500_ORDER_EACH_BET1_BET2_BET3"
        ),
    }
)
SOURCE_CANDIDATE_K_VALUES_BY_METHOD: Final = MappingProxyType(
    {
        ENSEMBLE_METHOD_ID: (8, 12, 49),
        BACKTEST_METHOD_ID: (8, 12, 49),
    }
)
RANDOM_PROTOCOL_BY_METHOD: Final = MappingProxyType(
    {
        ENSEMBLE_METHOD_ID: (
            "PYTHON_RANDOM_AND_NUMPY_RANDOM_RESET_TO_42_AT_EACH_TARGET"
        ),
        BACKTEST_METHOD_ID: (
            "PYTHON_RANDOM_AND_NUMPY_RANDOM_RESET_TO_123_AT_EACH_"
            "DIVERSIFIED_HORIZON_START"
        ),
    }
)
SOURCE_CLOSED_RESULT_HORIZONS_BY_METHOD: Final = MappingProxyType(
    {
        ENSEMBLE_METHOD_ID: (),
        BACKTEST_METHOD_ID: (150, 500),
    }
)
SOURCE_RANDOM_BASELINE_EXCLUDED_BY_METHOD: Final = MappingProxyType(
    {
        ENSEMBLE_METHOD_ID: False,
        BACKTEST_METHOD_ID: True,
    }
)
SOURCE_NATIVE_WAVE62_PROTOCOL = (
    "legacy_diversified_native_wave62/v1"
)
CAUSAL_PROTOCOL = (
    "FROZEN_DIVERSIFIED_SEED42_PER_TARGET_AND_"
    "BACKTEST_HORIZONS_150_500_SEED123_V1"
)
DEFAULT_SOURCE_NATIVE_WAVE62_USER_SEED = (
    "biglotto-full-universe-diversified-native-wave62-v1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
LEDGER_RESOURCE_NAME = (
    "biglotto_diversified_wave62_ticket_ledger_v1.json"
)
LEDGER_SCHEMA_VERSION = (
    "BIG_LOTTO_DIVERSIFIED_WAVE62_TICKET_LEDGER_V1"
)
LEDGER_FILE_SHA256 = (
    "223b593f391d3f9f9aafc1c494b7693e4e25a194c68c620a83c8ee822b1182e9"
)
LEDGER_CONTENT_SHA256 = (
    "e9425e15961b4d5733b6a1eaa5aac976229a6e55e3d7f1ecfcf27378f1e57f1c"
)
SOURCE_REFERENCE_RUNTIME = (
    "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_NETWORKX_3_2_1_"
    "ENSEMBLE_SEED42_PER_TARGET_AND_BACKTEST_SEED123_PER_HORIZON"
)
MODEL_CANDIDATE_K = 49
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"
CAUSAL_ELIGIBILITY_RULE = (
    "TARGET_USES_ONLY_THE_FULL_STRICTLY_EARLIER_DRAW_PREFIX"
)


class LegacyDiversifiedNativeWave62Error(ValueError):
    """A wave-62 request or packaged ledger violates its contract."""


class LegacyDiversifiedNativeWave62SourceError(
    LegacyDiversifiedNativeWave62Error
):
    """The frozen source has no legal portfolio for the target."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacyDiversifiedNativeWave62Request:
    legacy_method_id: str
    target_draw_number: str
    target_draw_date: date
    history: tuple[LegacyHistoryDraw, ...]
    dataset_sha256: str
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE62_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacyDiversifiedNativeWave62Metadata:
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
    source_candidate_k_values: tuple[int, ...]
    candidate_k: None
    native_ticket_count: int
    native_ticket_count_semantics: str
    native_ticket_order: str
    native_duplicate_ticket_count: int
    combination_count: None
    local_configuration_count: int
    source_closed_result_horizons: tuple[int, ...]
    source_random_baseline_excluded: bool
    causal_eligibility_rule: str
    source_reference_runtime: str
    ledger_schema_version: str
    ledger_file_sha256: str
    ledger_content_sha256: str
    ledger_target_index: int

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacyDiversifiedNativeWave62Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacyDiversifiedNativeWave62Metadata


@dataclass(frozen=True, slots=True)
class _Ledger:
    targets: tuple[str, ...]
    target_index: MappingProxyType[str, int]
    context_sha256: tuple[str, ...]
    tickets_by_method: MappingProxyType[
        str,
        tuple[tuple[Ticket, ...] | None, ...],
    ]
    closed_reason_by_method: MappingProxyType[
        str,
        tuple[str | None, ...],
    ]
    configuration_count_by_method: MappingProxyType[
        str,
        tuple[int | None, ...],
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
        raise LegacyDiversifiedNativeWave62Error(
            "packaged wave-62 ticket must be an array"
        )
    values = cast(list[object], value)
    if not all(type(number) is int for number in values):
        raise LegacyDiversifiedNativeWave62Error(
            "packaged wave-62 ticket must contain integers"
        )
    integers = cast(list[int], values)
    if (
        len(integers) != 6
        or integers != sorted(integers)
        or len(set(integers)) != 6
        or any(not 1 <= number <= 49 for number in integers)
    ):
        raise LegacyDiversifiedNativeWave62Error(
            "packaged wave-62 ticket is not a sorted legal ticket"
        )
    return cast(Ticket, tuple(integers))


def _method_sequence(
    document: dict[str, Any],
    *,
    key: str,
    method_id: str,
) -> list[object]:
    mapping = document.get(key)
    if not isinstance(mapping, dict):
        raise LegacyDiversifiedNativeWave62Error(
            f"packaged wave-62 {key} must be an object"
        )
    value = cast(dict[str, object], mapping).get(method_id)
    if not isinstance(value, list):
        raise LegacyDiversifiedNativeWave62Error(
            f"packaged wave-62 {key} method sequence changed"
        )
    return cast(list[object], value)


@lru_cache(maxsize=1)
def _load_ledger() -> _Ledger:
    raw = (
        files("lottolab.strategies.data")
        .joinpath(LEDGER_RESOURCE_NAME)
        .read_bytes()
    )
    if hashlib.sha256(raw).hexdigest() != LEDGER_FILE_SHA256:
        raise LegacyDiversifiedNativeWave62Error(
            "packaged wave-62 ledger file SHA changed"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacyDiversifiedNativeWave62Error(
            "packaged wave-62 ledger is invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise LegacyDiversifiedNativeWave62Error(
            "packaged wave-62 ledger must be an object"
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
        or document.get("source_sha256_by_method")
        != dict(SOURCE_SHA256_BY_METHOD)
        or document.get("causal_eligibility_rule")
        != CAUSAL_ELIGIBILITY_RULE
    ):
        raise LegacyDiversifiedNativeWave62Error(
            "packaged wave-62 ledger identity changed"
        )
    targets_raw = cast(
        list[object],
        document.get("target_draw_numbers", []),
    )
    contexts_raw = cast(
        list[object],
        document.get("context_numbers_sha256_by_target", []),
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
        raise LegacyDiversifiedNativeWave62Error(
            "packaged wave-62 target identity changed"
        )
    tickets_by_method: dict[
        str,
        tuple[tuple[Ticket, ...] | None, ...],
    ] = {}
    reasons_by_method: dict[str, tuple[str | None, ...]] = {}
    configs_by_method: dict[str, tuple[int | None, ...]] = {}
    for method_id in SUPPORTED_METHODS:
        tickets_raw = _method_sequence(
            document,
            key="tickets_by_method",
            method_id=method_id,
        )
        reasons_raw = _method_sequence(
            document,
            key="closed_reason_by_method",
            method_id=method_id,
        )
        configs_raw = _method_sequence(
            document,
            key="configuration_count_by_method",
            method_id=method_id,
        )
        if not (
            len(tickets_raw)
            == len(reasons_raw)
            == len(configs_raw)
            == 2149
        ):
            raise LegacyDiversifiedNativeWave62Error(
                "packaged wave-62 method coverage changed"
            )
        portfolios: list[tuple[Ticket, ...] | None] = []
        reasons: list[str | None] = []
        configs: list[int | None] = []
        for portfolio_raw, reason, config in zip(
            tickets_raw,
            reasons_raw,
            configs_raw,
            strict=True,
        ):
            if portfolio_raw is None:
                if not isinstance(reason, str) or config is not None:
                    raise LegacyDiversifiedNativeWave62Error(
                        "packaged wave-62 closure changed"
                    )
                portfolios.append(None)
                reasons.append(reason)
                configs.append(None)
                continue
            if (
                not isinstance(portfolio_raw, list)
                or reason is not None
                or type(config) is not int
            ):
                raise LegacyDiversifiedNativeWave62Error(
                    "packaged wave-62 executable row changed"
                )
            portfolio = tuple(
                _ticket(ticket)
                for ticket in cast(list[object], portfolio_raw)
            )
            if (
                config not in {1, 2}
                or len(portfolio) != 3 * config
                or (
                    method_id == ENSEMBLE_METHOD_ID
                    and config != 1
                )
            ):
                raise LegacyDiversifiedNativeWave62Error(
                    "packaged wave-62 native semantics changed"
                )
            portfolios.append(portfolio)
            reasons.append(None)
            configs.append(config)
        tickets_by_method[method_id] = tuple(portfolios)
        reasons_by_method[method_id] = tuple(reasons)
        configs_by_method[method_id] = tuple(configs)
    targets = cast(tuple[str, ...], tuple(targets_raw))
    return _Ledger(
        targets=targets,
        target_index=MappingProxyType(
            {
                target: index
                for index, target in enumerate(targets)
            }
        ),
        context_sha256=cast(tuple[str, ...], tuple(contexts_raw)),
        tickets_by_method=MappingProxyType(tickets_by_method),
        closed_reason_by_method=MappingProxyType(reasons_by_method),
        configuration_count_by_method=MappingProxyType(
            configs_by_method
        ),
    )


def load_legacy_diversified_native_wave62_ledger_for_verification() -> (
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


def generate_legacy_diversified_native_wave62_portfolio(
    request: LegacyDiversifiedNativeWave62Request,
) -> LegacyDiversifiedNativeWave62Result:
    """Replay one frozen diversified target portfolio."""

    if (
        request.legacy_method_id not in SUPPORTED_METHODS
        or type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.target_draw_date) is not date
        or request.dataset_sha256 != PINNED_DATASET_SHA256
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
    ):
        raise LegacyDiversifiedNativeWave62Error(
            "invalid wave-62 request identity"
        )
    ledger = _load_ledger()
    target_index = ledger.target_index.get(request.target_draw_number)
    if target_index is None:
        raise LegacyDiversifiedNativeWave62SourceError(
            "TARGET_OUTSIDE_FROZEN_WAVE62_TICKET_LEDGER"
        )
    context_sha256 = _context_sha256(request.history)
    if context_sha256 != ledger.context_sha256[target_index]:
        raise LegacyDiversifiedNativeWave62SourceError(
            "FROZEN_WAVE62_FULL_PREFIX_CONTEXT_MISMATCH"
        )
    tickets = ledger.tickets_by_method[
        request.legacy_method_id
    ][target_index]
    if tickets is None:
        raise LegacyDiversifiedNativeWave62SourceError(
            ledger.closed_reason_by_method[
                request.legacy_method_id
            ][target_index]
            or "FROZEN_WAVE62_CLOSED_WITHOUT_REASON"
        )
    configuration_count = ledger.configuration_count_by_method[
        request.legacy_method_id
    ][target_index]
    if configuration_count is None or not request.history:
        raise LegacyDiversifiedNativeWave62Error(
            "executable wave-62 row lacks causal configuration state"
        )
    seed_integer = (
        42
        if request.legacy_method_id == ENSEMBLE_METHOD_ID
        else 123
    )
    seed_material = (
        f"{request.legacy_method_id};seed={seed_integer};"
        f"target_index={target_index};"
        f"local_configuration_count={configuration_count};"
        f"horizons={SOURCE_CLOSED_RESULT_HORIZONS_BY_METHOD[request.legacy_method_id]}"
    )
    return LegacyDiversifiedNativeWave62Result(
        tickets=tickets,
        metadata=LegacyDiversifiedNativeWave62Metadata(
            protocol=SOURCE_NATIVE_WAVE62_PROTOCOL,
            causal_protocol=CAUSAL_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=SOURCE_SHA256_BY_METHOD[
                request.legacy_method_id
            ],
            target_draw_number=request.target_draw_number,
            target_draw_date=request.target_draw_date.isoformat(),
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=hashlib.sha256(
                seed_material.encode("utf-8")
            ).hexdigest(),
            seed_integer=seed_integer,
            random_protocol=RANDOM_PROTOCOL_BY_METHOD[
                request.legacy_method_id
            ],
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
                "AT_PUBLIC_ENTRYPOINT_THEN_SOURCE_DATE_ASC_SORT"
            ),
            context_draw_count=len(request.history),
            context_numbers_sha256=context_sha256,
            source_candidate_k_values=(
                SOURCE_CANDIDATE_K_VALUES_BY_METHOD[
                    request.legacy_method_id
                ]
            ),
            candidate_k=None,
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_order=NATIVE_TICKET_ORDER_BY_METHOD[
                request.legacy_method_id
            ],
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            combination_count=None,
            local_configuration_count=configuration_count,
            source_closed_result_horizons=(
                SOURCE_CLOSED_RESULT_HORIZONS_BY_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_random_baseline_excluded=(
                SOURCE_RANDOM_BASELINE_EXCLUDED_BY_METHOD[
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
    "BACKTEST_METHOD_ID",
    "CAUSAL_ELIGIBILITY_RULE",
    "CAUSAL_PROTOCOL",
    "CONTEXT_POLICY",
    "DEFAULT_SOURCE_NATIVE_WAVE62_USER_SEED",
    "ENSEMBLE_METHOD_ID",
    "FROZEN_SOURCE_COMMIT",
    "LEDGER_CONTENT_SHA256",
    "LEDGER_FILE_SHA256",
    "LEDGER_RESOURCE_NAME",
    "LEDGER_SCHEMA_VERSION",
    "MODEL_CANDIDATE_K",
    "NATIVE_TICKET_ORDER_BY_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_METHOD",
    "PINNED_DATASET_SHA256",
    "RANDOM_PROTOCOL_BY_METHOD",
    "SOURCE_CANDIDATE_K_VALUES_BY_METHOD",
    "SOURCE_CLOSED_RESULT_HORIZONS_BY_METHOD",
    "SOURCE_NATIVE_WAVE62_PROTOCOL",
    "SOURCE_RANDOM_BASELINE_EXCLUDED_BY_METHOD",
    "SOURCE_REFERENCE_RUNTIME",
    "SOURCE_SHA256_BY_METHOD",
    "SUPPORTED_METHODS",
    "LegacyDiversifiedNativeWave62Error",
    "LegacyDiversifiedNativeWave62Metadata",
    "LegacyDiversifiedNativeWave62Request",
    "LegacyDiversifiedNativeWave62Result",
    "LegacyDiversifiedNativeWave62SourceError",
    "generate_legacy_diversified_native_wave62_portfolio",
    "load_legacy_diversified_native_wave62_ledger_for_verification",
]
