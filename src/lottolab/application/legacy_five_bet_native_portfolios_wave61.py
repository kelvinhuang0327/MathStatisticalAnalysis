"""Frozen closed-result five-bet benchmark replay for wave 61."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from functools import lru_cache
from importlib.resources import files
from types import MappingProxyType
from typing import Any, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

METHOD_ID = "tools/test_5bet_optimization.py"
SOURCE_SHA256 = (
    "987f6c374c0904ecadc91105db82d8887126a7c22ca0af08a10ac881753b8c4d"
)
SOURCE_NATIVE_WAVE61_PROTOCOL = "legacy_five_bet_native_wave61/v1"
CAUSAL_PROTOCOL = (
    "FROZEN_SOURCE_CLOSED_RESULT_HORIZONS_150_200_SEED42_V1"
)
DEFAULT_SOURCE_NATIVE_WAVE61_USER_SEED = (
    "biglotto-full-universe-five-bet-native-wave61-v1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
LEDGER_RESOURCE_NAME = "biglotto_five_bet_wave61_ticket_ledger_v1.json"
LEDGER_SCHEMA_VERSION = (
    "BIG_LOTTO_FIVE_BET_WAVE61_TICKET_LEDGER_V1"
)
LEDGER_FILE_SHA256 = (
    "b20c1aadef9c63c3918d461f69790bdee77e6b8d1b883ea9a57a4d6719340810"
)
LEDGER_CONTENT_SHA256 = (
    "6f30be57e92a71d6aa3570d84b71af9ef844949dad72ca9e36b39390d6944a7d"
)
SOURCE_REFERENCE_RUNTIME = (
    "CPYTHON_3_9_6_NUMPY_1_26_2_SOURCE_RUN_BENCHMARK_SEED42"
)
MODEL_CANDIDATE_K = 49
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"
CAUSAL_ELIGIBILITY_RULE = (
    "TARGET_USES_ONLY_THE_FULL_STRICTLY_EARLIER_DRAW_PREFIX"
)
OUTSIDE_HORIZON_REASON = (
    "OUTSIDE_FROZEN_SOURCE_CLOSED_RESULT_HORIZONS_150_200"
)
NATIVE_TICKET_SEMANTICS = (
    "SOURCE_MAIN_CALL_ORDER_5ME_P150_4P1_P150_5ME_P200_"
    "4P1_P200_DENSE_P200_WITH_15_OR_25_POSITIONAL_TICKETS"
)


class LegacyFiveBetNativeWave61Error(ValueError):
    """A wave-61 request or packaged ledger violates its contract."""


class LegacyFiveBetNativeWave61SourceError(
    LegacyFiveBetNativeWave61Error
):
    """The frozen closed-result source has no legal target portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacyFiveBetNativeWave61Request:
    target_draw_number: str
    target_draw_date: date
    history: tuple[LegacyHistoryDraw, ...]
    dataset_sha256: str
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE61_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacyFiveBetNativeWave61Metadata:
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
    source_closed_result_horizons: tuple[int, int]
    causal_eligibility_rule: str
    source_reference_runtime: str
    ledger_schema_version: str
    ledger_file_sha256: str
    ledger_content_sha256: str
    ledger_target_index: int

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacyFiveBetNativeWave61Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacyFiveBetNativeWave61Metadata


@dataclass(frozen=True, slots=True)
class _Ledger:
    targets: tuple[str, ...]
    target_index: MappingProxyType[str, int]
    context_sha256: tuple[str, ...]
    tickets: tuple[tuple[Ticket, ...] | None, ...]
    closed_reason: tuple[str | None, ...]
    local_configuration_count: tuple[int | None, ...]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _ticket(value: object) -> Ticket:
    if not isinstance(value, list):
        raise LegacyFiveBetNativeWave61Error(
            "packaged wave-61 ticket must be an array"
        )
    values = cast(list[object], value)
    if not all(type(number) is int for number in values):
        raise LegacyFiveBetNativeWave61Error(
            "packaged wave-61 ticket must contain integers"
        )
    integers = cast(list[int], values)
    if (
        len(integers) != 6
        or integers != sorted(integers)
        or len(set(integers)) != 6
        or any(not 1 <= number <= 49 for number in integers)
    ):
        raise LegacyFiveBetNativeWave61Error(
            "packaged wave-61 ticket is not a sorted legal ticket"
        )
    return cast(Ticket, tuple(integers))


@lru_cache(maxsize=1)
def _load_ledger() -> _Ledger:
    raw = (
        files("lottolab.strategies.data")
        .joinpath(LEDGER_RESOURCE_NAME)
        .read_bytes()
    )
    if hashlib.sha256(raw).hexdigest() != LEDGER_FILE_SHA256:
        raise LegacyFiveBetNativeWave61Error(
            "packaged wave-61 ledger file SHA changed"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacyFiveBetNativeWave61Error(
            "packaged wave-61 ledger is invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise LegacyFiveBetNativeWave61Error(
            "packaged wave-61 ledger must be an object"
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
        or document.get("legacy_method_id") != METHOD_ID
        or document.get("source_sha256") != SOURCE_SHA256
        or document.get("causal_protocol") != CAUSAL_PROTOCOL
    ):
        raise LegacyFiveBetNativeWave61Error(
            "packaged wave-61 ledger identity changed"
        )
    targets_raw = cast(list[object], document.get("targets", []))
    contexts_raw = cast(
        list[object],
        document.get("context_sha256", []),
    )
    tickets_raw = cast(list[object], document.get("tickets", []))
    reasons_raw = cast(
        list[object],
        document.get("closed_reason", []),
    )
    configs_raw = cast(
        list[object],
        document.get("local_configuration_count", []),
    )
    if not (
        len(targets_raw)
        == len(contexts_raw)
        == len(tickets_raw)
        == len(reasons_raw)
        == len(configs_raw)
        == 2149
    ):
        raise LegacyFiveBetNativeWave61Error(
            "packaged wave-61 coverage changed"
        )
    if (
        not all(isinstance(value, str) for value in targets_raw)
        or not all(
            isinstance(value, str) and len(value) == 64
            for value in contexts_raw
        )
    ):
        raise LegacyFiveBetNativeWave61Error(
            "packaged wave-61 target identity changed"
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
                raise LegacyFiveBetNativeWave61Error(
                    "packaged wave-61 closure changed"
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
            raise LegacyFiveBetNativeWave61Error(
                "packaged wave-61 executable row changed"
            )
        portfolio = tuple(
            _ticket(ticket)
            for ticket in cast(list[object], portfolio_raw)
        )
        if len(portfolio) not in {15, 25} or config not in {3, 5}:
            raise LegacyFiveBetNativeWave61Error(
                "packaged wave-61 native semantics changed"
            )
        portfolios.append(portfolio)
        reasons.append(None)
        configs.append(config)
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
        tickets=tuple(portfolios),
        closed_reason=tuple(reasons),
        local_configuration_count=tuple(configs),
    )


def load_legacy_five_bet_native_wave61_ledger_for_verification() -> (
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


def generate_legacy_five_bet_native_wave61_portfolio(
    request: LegacyFiveBetNativeWave61Request,
) -> LegacyFiveBetNativeWave61Result:
    """Replay one source-declared closed-result five-bet portfolio."""

    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.target_draw_date) is not date
        or type(request.dataset_sha256) is not str or not request.dataset_sha256
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
    ):
        raise LegacyFiveBetNativeWave61Error(
            "invalid wave-61 request identity"
        )
    ledger = _load_ledger()
    target_index = ledger.target_index.get(request.target_draw_number)
    if target_index is None:
        raise LegacyFiveBetNativeWave61SourceError(
            "TARGET_OUTSIDE_FROZEN_WAVE61_TICKET_LEDGER"
        )
    context_sha256 = _context_sha256(request.history)
    if context_sha256 != ledger.context_sha256[target_index]:
        raise LegacyFiveBetNativeWave61SourceError(
            "FROZEN_WAVE61_FULL_PREFIX_CONTEXT_MISMATCH"
        )
    tickets = ledger.tickets[target_index]
    if tickets is None:
        raise LegacyFiveBetNativeWave61SourceError(
            ledger.closed_reason[target_index]
            or "FROZEN_WAVE61_CLOSED_WITHOUT_REASON"
        )
    configuration_count = ledger.local_configuration_count[target_index]
    if configuration_count is None or not request.history:
        raise LegacyFiveBetNativeWave61Error(
            "executable wave-61 row lacks causal configuration state"
        )
    seed_material = (
        "run_benchmark:set_seed(42);source_main_call_order;"
        f"local_configuration_count={configuration_count}"
    )
    return LegacyFiveBetNativeWave61Result(
        tickets=tickets,
        metadata=LegacyFiveBetNativeWave61Metadata(
            protocol=SOURCE_NATIVE_WAVE61_PROTOCOL,
            causal_protocol=CAUSAL_PROTOCOL,
            legacy_method_id=METHOD_ID,
            source_sha256=SOURCE_SHA256,
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
                "SOURCE_RUN_BENCHMARK_RESETS_PYTHON_AND_NUMPY_SEED42_"
                "ONCE_PER_DECLARED_HORIZON_CONFIGURATION_RUN"
            ),
            randomness_used=True,
            randomness_reproduction=(
                "SOURCE_RUNTIME_LEDGER_EXACT_TICKET_REPLAY"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="OLDEST_FIRST",
            context_draw_count=len(request.history),
            context_numbers_sha256=context_sha256,
            source_candidate_k_values=(18, 20, 49),
            candidate_k=None,
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=NATIVE_TICKET_SEMANTICS,
            native_ticket_order=(
                "SOURCE_MAIN_CONFIGURATION_CALL_ORDER_THEN_BET_POSITION"
            ),
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            combination_count=None,
            local_configuration_count=configuration_count,
            source_closed_result_horizons=(150, 200),
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
    "DEFAULT_SOURCE_NATIVE_WAVE61_USER_SEED",
    "FROZEN_SOURCE_COMMIT",
    "LEDGER_CONTENT_SHA256",
    "LEDGER_FILE_SHA256",
    "LEDGER_RESOURCE_NAME",
    "LEDGER_SCHEMA_VERSION",
    "METHOD_ID",
    "MODEL_CANDIDATE_K",
    "NATIVE_TICKET_SEMANTICS",
    "OUTSIDE_HORIZON_REASON",
    "PINNED_DATASET_SHA256",
    "SOURCE_NATIVE_WAVE61_PROTOCOL",
    "SOURCE_REFERENCE_RUNTIME",
    "SOURCE_SHA256",
    "LegacyFiveBetNativeWave61Error",
    "LegacyFiveBetNativeWave61Metadata",
    "LegacyFiveBetNativeWave61Request",
    "LegacyFiveBetNativeWave61Result",
    "LegacyFiveBetNativeWave61SourceError",
    "generate_legacy_five_bet_native_wave61_portfolio",
    "load_legacy_five_bet_native_wave61_ledger_for_verification",
]
