"""Frozen target-stable advanced-method portfolio replay for wave 63."""

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

METHOD_ID = "tools/advanced_methods_benchmark.py"
SOURCE_SHA256 = (
    "87ee0d15033c8873c7cf4c1f7334fc154dbab434703195cc4e90810169ea620f"
)
SOURCE_NATIVE_WAVE63_PROTOCOL = (
    "legacy_advanced_methods_native_wave63/v1"
)
CAUSAL_PROTOCOL = (
    "FROZEN_LOCAL_SELECTORS_TARGET_STABLE_SEED42_"
    "RECENT1000_METHOD_ORDER_X_2_THEN_3_BETS_V1"
)
DEFAULT_SOURCE_NATIVE_WAVE63_USER_SEED = (
    "biglotto-full-universe-advanced-methods-native-wave63-v1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
LEDGER_RESOURCE_NAME = (
    "biglotto_advanced_methods_wave63_ticket_ledger_v1.json"
)
LEDGER_SCHEMA_VERSION = (
    "BIG_LOTTO_ADVANCED_METHODS_WAVE63_TICKET_LEDGER_V1"
)
LEDGER_FILE_SHA256 = (
    "f98ad62752c35bcf47fe00338f8e8b4ddd1f39caa73a80405409c963a8651d04"
)
LEDGER_CONTENT_SHA256 = (
    "e168ef2d3176bbc62056fd54351a9eba4506ad7b841838d969107eace8b6cf34"
)
SOURCE_REFERENCE_RUNTIME = (
    "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_12_0_"
    "TARGET_STABLE_LOCAL_SELECTOR_REINSTANTIATION_SEED42"
)
MODEL_CANDIDATE_K = 49
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"
CAUSAL_ELIGIBILITY_RULE = (
    "TARGET_USES_ONLY_STRICTLY_EARLIER_DRAWS_WITH_SOURCE_RECENT1000_LIMIT"
)
FIRST_TARGET_REASON = "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF"
METHOD_ORDER = (
    "Contextual Bandit",
    "Copula Analysis",
    "Anomaly Detection",
    "Graph PageRank",
    "Attention Scorer",
)
NATIVE_TICKET_SEMANTICS = (
    "SOURCE_BIG_LOTTO_NUM_BETS_2_THEN_3_EACH_FIVE_LOCAL_"
    "METHODS_IN_DECLARATION_ORDER_FLATTENED_TO_25_POSITIONAL_TICKETS"
)
NATIVE_TICKET_ORDER = (
    "NUM_BETS_2_METHOD_DECLARATION_ORDER_THEN_NUM_BETS_"
    "3_METHOD_DECLARATION_ORDER_EACH_REPEATED_BET_POSITION"
)
RANDOM_PROTOCOL = (
    "PYTHON_RANDOM_AND_NUMPY_RANDOM_RESET_TO_42_AT_"
    "EACH_TARGET_BEFORE_LOCAL_METHOD_BLOCKS"
)


class LegacyAdvancedMethodsNativeWave63Error(ValueError):
    """A wave-63 request or packaged ledger violates its contract."""


class LegacyAdvancedMethodsNativeWave63SourceError(
    LegacyAdvancedMethodsNativeWave63Error
):
    """The frozen causal adapter has no portfolio for the target."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacyAdvancedMethodsNativeWave63Request:
    target_draw_number: str
    target_draw_date: date
    history: tuple[LegacyHistoryDraw, ...]
    dataset_sha256: str
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE63_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacyAdvancedMethodsNativeWave63Metadata:
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
    source_history_input_draw_count: int
    source_history_input_upper_bound: int
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
    local_method_order: tuple[str, ...]
    source_main_reverse_chronological_state_reuse_excluded: bool
    source_random_baseline_excluded: bool
    target_stable_reinstantiation: bool
    causal_eligibility_rule: str
    source_reference_runtime: str
    ledger_schema_version: str
    ledger_file_sha256: str
    ledger_content_sha256: str
    ledger_target_index: int

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacyAdvancedMethodsNativeWave63Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacyAdvancedMethodsNativeWave63Metadata


@dataclass(frozen=True, slots=True)
class _Ledger:
    targets: tuple[str, ...]
    target_index: MappingProxyType[str, int]
    context_sha256: tuple[str, ...]
    history_input_draw_count: tuple[int, ...]
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
        raise LegacyAdvancedMethodsNativeWave63Error(
            "packaged wave-63 ticket must be an array"
        )
    values = cast(list[object], value)
    if not all(type(number) is int for number in values):
        raise LegacyAdvancedMethodsNativeWave63Error(
            "packaged wave-63 ticket must contain integers"
        )
    integers = cast(list[int], values)
    if (
        len(integers) != 6
        or integers != sorted(integers)
        or len(set(integers)) != 6
        or any(not 1 <= number <= 49 for number in integers)
    ):
        raise LegacyAdvancedMethodsNativeWave63Error(
            "packaged wave-63 ticket is not a sorted legal ticket"
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
        raise LegacyAdvancedMethodsNativeWave63Error(
            "packaged wave-63 ledger file SHA changed"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacyAdvancedMethodsNativeWave63Error(
            "packaged wave-63 ledger is invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise LegacyAdvancedMethodsNativeWave63Error(
            "packaged wave-63 ledger must be an object"
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
        or document.get("causal_eligibility_rule")
        != CAUSAL_ELIGIBILITY_RULE
    ):
        raise LegacyAdvancedMethodsNativeWave63Error(
            "packaged wave-63 ledger identity changed"
        )
    targets_raw = cast(
        list[object],
        document.get("target_draw_numbers", []),
    )
    contexts_raw = cast(
        list[object],
        document.get("context_numbers_sha256_by_target", []),
    )
    counts_raw = cast(
        list[object],
        document.get("history_input_draw_count", []),
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
        == len(counts_raw)
        == len(tickets_raw)
        == len(reasons_raw)
        == len(configs_raw)
        == 2149
    ):
        raise LegacyAdvancedMethodsNativeWave63Error(
            "packaged wave-63 coverage changed"
        )
    if (
        not all(isinstance(value, str) for value in targets_raw)
        or not all(
            isinstance(value, str) and len(value) == 64
            for value in contexts_raw
        )
        or not all(
            type(value) is int
            and value == min(index, 1000)
            for index, value in enumerate(counts_raw)
        )
    ):
        raise LegacyAdvancedMethodsNativeWave63Error(
            "packaged wave-63 target identity changed"
        )
    portfolios: list[tuple[Ticket, ...] | None] = []
    reasons: list[str | None] = []
    configs: list[int | None] = []
    for index, (portfolio_raw, reason, config) in enumerate(
        zip(tickets_raw, reasons_raw, configs_raw, strict=True)
    ):
        if index == 0:
            if (
                portfolio_raw is not None
                or reason != FIRST_TARGET_REASON
                or config is not None
            ):
                raise LegacyAdvancedMethodsNativeWave63Error(
                    "packaged wave-63 first closure changed"
                )
            portfolios.append(None)
            reasons.append(FIRST_TARGET_REASON)
            configs.append(None)
            continue
        if (
            not isinstance(portfolio_raw, list)
            or reason is not None
            or config != 10
        ):
            raise LegacyAdvancedMethodsNativeWave63Error(
                "packaged wave-63 executable row changed"
            )
        portfolio = tuple(
            _ticket(ticket)
            for ticket in cast(list[object], portfolio_raw)
        )
        if len(portfolio) != 25:
            raise LegacyAdvancedMethodsNativeWave63Error(
                "packaged wave-63 native semantics changed"
            )
        portfolios.append(portfolio)
        reasons.append(None)
        configs.append(10)
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
        history_input_draw_count=cast(
            tuple[int, ...],
            tuple(counts_raw),
        ),
        tickets=tuple(portfolios),
        closed_reason=tuple(reasons),
        local_configuration_count=tuple(configs),
    )


def load_legacy_advanced_methods_native_wave63_ledger_for_verification() -> (
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


def generate_legacy_advanced_methods_native_wave63_portfolio(
    request: LegacyAdvancedMethodsNativeWave63Request,
) -> LegacyAdvancedMethodsNativeWave63Result:
    """Replay one target-stable causal advanced-method portfolio."""

    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.target_draw_date) is not date
        or type(request.dataset_sha256) is not str or not request.dataset_sha256
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
    ):
        raise LegacyAdvancedMethodsNativeWave63Error(
            "invalid wave-63 request identity"
        )
    ledger = _load_ledger()
    target_index = ledger.target_index.get(request.target_draw_number)
    if target_index is None:
        raise LegacyAdvancedMethodsNativeWave63SourceError(
            "TARGET_OUTSIDE_FROZEN_WAVE63_TICKET_LEDGER"
        )
    context_sha256 = _context_sha256(request.history)
    if context_sha256 != ledger.context_sha256[target_index]:
        raise LegacyAdvancedMethodsNativeWave63SourceError(
            "FROZEN_WAVE63_FULL_PREFIX_CONTEXT_MISMATCH"
        )
    tickets = ledger.tickets[target_index]
    if tickets is None:
        raise LegacyAdvancedMethodsNativeWave63SourceError(
            ledger.closed_reason[target_index]
            or "FROZEN_WAVE63_CLOSED_WITHOUT_REASON"
        )
    configuration_count = ledger.local_configuration_count[target_index]
    if configuration_count != 10 or not request.history:
        raise LegacyAdvancedMethodsNativeWave63Error(
            "executable wave-63 row lacks causal configuration state"
        )
    seed_material = (
        "target_stable_random.seed(42);numpy.random.seed(42);"
        "num_bets=2,3;method_order="
        + ",".join(METHOD_ORDER)
    )
    return LegacyAdvancedMethodsNativeWave63Result(
        tickets=tickets,
        metadata=LegacyAdvancedMethodsNativeWave63Metadata(
            protocol=SOURCE_NATIVE_WAVE63_PROTOCOL,
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
            random_protocol=RANDOM_PROTOCOL,
            randomness_used=True,
            randomness_reproduction=(
                "SOURCE_RUNTIME_LEDGER_EXACT_TICKET_REPLAY"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="RECENT_FIRST",
            source_history_order_detail=(
                "FULL_STRICT_PREFIX_LIMITED_TO_MOST_RECENT_1000_"
                "THEN_REVERSED_FOR_FROZEN_LOCAL_SELECTORS"
            ),
            source_history_input_draw_count=(
                ledger.history_input_draw_count[target_index]
            ),
            source_history_input_upper_bound=1000,
            context_draw_count=len(request.history),
            context_numbers_sha256=context_sha256,
            source_candidate_k_values=(49,),
            candidate_k=None,
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=NATIVE_TICKET_SEMANTICS,
            native_ticket_order=NATIVE_TICKET_ORDER,
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            combination_count=None,
            local_configuration_count=configuration_count,
            local_method_order=METHOD_ORDER,
            source_main_reverse_chronological_state_reuse_excluded=True,
            source_random_baseline_excluded=True,
            target_stable_reinstantiation=True,
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
    "DEFAULT_SOURCE_NATIVE_WAVE63_USER_SEED",
    "FIRST_TARGET_REASON",
    "FROZEN_SOURCE_COMMIT",
    "LEDGER_CONTENT_SHA256",
    "LEDGER_FILE_SHA256",
    "LEDGER_RESOURCE_NAME",
    "LEDGER_SCHEMA_VERSION",
    "METHOD_ID",
    "METHOD_ORDER",
    "MODEL_CANDIDATE_K",
    "NATIVE_TICKET_ORDER",
    "NATIVE_TICKET_SEMANTICS",
    "PINNED_DATASET_SHA256",
    "RANDOM_PROTOCOL",
    "SOURCE_NATIVE_WAVE63_PROTOCOL",
    "SOURCE_REFERENCE_RUNTIME",
    "SOURCE_SHA256",
    "LegacyAdvancedMethodsNativeWave63Error",
    "LegacyAdvancedMethodsNativeWave63Metadata",
    "LegacyAdvancedMethodsNativeWave63Request",
    "LegacyAdvancedMethodsNativeWave63Result",
    "LegacyAdvancedMethodsNativeWave63SourceError",
    "generate_legacy_advanced_methods_native_wave63_portfolio",
    "load_legacy_advanced_methods_native_wave63_ledger_for_verification",
]
