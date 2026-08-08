"""Checksummed frozen XGBoost native-ticket replay for wave 64."""

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

METHOD_ID = "lottery_api/models/xgboost_model.py"
SOURCE_SHA256 = (
    "38c72a70c627285dab2b55163b387b3ed8ab6bd9820c10d7daed0dce777f1c01"
)
SOURCE_NATIVE_WAVE64_PROTOCOL = "legacy_xgboost_native_wave64/v1"
CAUSAL_PROTOCOL = (
    "FROZEN_XGBOOST_PREDICT_STRICT_PREFIX_RECENT1000_"
    "XGBOOST_2_0_2_SKLEARN_1_3_2_V1"
)
DEFAULT_SOURCE_NATIVE_WAVE64_USER_SEED = (
    "biglotto-full-universe-xgboost-native-wave64-v1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
LEDGER_RESOURCE_NAME = "biglotto_xgboost_wave64_ticket_ledger_v1.json"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_XGBOOST_WAVE64_TICKET_LEDGER_V1"
LEDGER_FILE_SHA256 = (
    "0e2946ccf9a803488afd5475e833bd557a40bf93e5d1cb26e912a29926b1a9ba"
)
LEDGER_CONTENT_SHA256 = (
    "e227e6c3aafb859fb56afaee99e0f1ab31cb792d8747ea972e2d959149810908"
)
TICKET_SEQUENCE_SHA256 = (
    "1d9752141cdc71301c7410b015bbbf6ca6dd522a687d6171da3def2b139a36df"
)
PROBABILITY_SEQUENCE_SHA256 = (
    "c35cda28dda4b45e0455842d07fa0d6db5224bc0a3281125ad919ecab600dc95"
)
SOURCE_REFERENCE_RUNTIME = (
    "CPYTHON_3_9_6_NUMPY_1_26_2_PANDAS_2_1_3_"
    "SKLEARN_1_3_2_XGBOOST_2_0_2"
)
MODEL_CANDIDATE_K = 49
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"
CAUSAL_ELIGIBILITY_RULE = (
    "TARGET_USES_ONLY_STRICTLY_EARLIER_DRAWS_WITH_SOURCE_RECENT1000_LIMIT"
)
CLOSED_REASON = "TRAINING_DATA_INSUFFICIENT_LT_15_HISTORY_DRAWS"
NATIVE_TICKET_SEMANTICS = (
    "FROZEN_SOURCE_NATIVE_ONE_TOP6_TICKET_FROM_49_MULTI_OUTPUT_"
    "BINARY_XGBOOST_PROBABILITIES"
)
NATIVE_TICKET_ORDER = "SINGLE_SOURCE_TICKET_SORTED_ASCENDING"
DETERMINISM_PROTOCOL = (
    "SOURCE_RANDOM_STATE_OMITTED_WITH_FULL_ROW_AND_COLUMN_SAMPLING_"
    "REPEAT_AND_OMP_1_VS_8_PARITY_PASS"
)


class LegacyXGBoostNativeWave64Error(ValueError):
    """A wave-64 request or packaged ledger violates its contract."""


class LegacyXGBoostNativeWave64SourceError(
    LegacyXGBoostNativeWave64Error
):
    """The frozen source has no executable ticket for this target."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacyXGBoostNativeWave64Request:
    target_draw_number: str
    target_draw_date: date
    history: tuple[LegacyHistoryDraw, ...]
    dataset_sha256: str
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE64_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacyXGBoostNativeWave64Metadata:
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
    determinism_protocol: str
    randomness_used: bool
    source_random_state_explicit: bool
    repeatability_parity_passed: bool
    thread_count_parity_passed: bool
    history_draw_count: int
    history_first_draw_number: str
    history_cutoff_draw_number: str
    source_history_order: str
    source_history_input_draw_count: int
    source_history_input_upper_bound: int
    context_draw_count: int
    context_numbers_sha256: str
    model_label_count: int
    estimators_per_label: int
    model_max_depth: int
    source_candidate_k_values: tuple[int, ...]
    candidate_k: None
    native_ticket_count: int
    native_ticket_count_semantics: str
    native_ticket_order: str
    native_duplicate_ticket_count: int
    combination_count: None
    local_configuration_count: int
    selected_probabilities: tuple[float, ...]
    confidence: float
    causal_eligibility_rule: str
    source_reference_runtime: str
    ledger_schema_version: str
    ledger_file_sha256: str
    ledger_content_sha256: str
    ledger_target_index: int

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacyXGBoostNativeWave64Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacyXGBoostNativeWave64Metadata


@dataclass(frozen=True, slots=True)
class _Ledger:
    targets: tuple[str, ...]
    target_index: MappingProxyType[str, int]
    context_sha256: tuple[str, ...]
    history_input_draw_count: tuple[int, ...]
    tickets: tuple[tuple[Ticket, ...] | None, ...]
    probabilities: tuple[tuple[float, ...] | None, ...]
    confidences: tuple[float | None, ...]
    closed_reason: tuple[str | None, ...]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _ticket(value: object) -> Ticket:
    if not isinstance(value, list):
        raise LegacyXGBoostNativeWave64Error(
            "packaged wave-64 ticket must be an array"
        )
    values = cast(list[object], value)
    if not all(type(number) is int for number in values):
        raise LegacyXGBoostNativeWave64Error(
            "packaged wave-64 ticket must contain integers"
        )
    integers = cast(list[int], values)
    if (
        len(integers) != 6
        or integers != sorted(integers)
        or len(set(integers)) != 6
        or any(not 1 <= number <= 49 for number in integers)
    ):
        raise LegacyXGBoostNativeWave64Error(
            "packaged wave-64 ticket is not a sorted legal ticket"
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
        raise LegacyXGBoostNativeWave64Error(
            "packaged wave-64 ledger file SHA changed"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacyXGBoostNativeWave64Error(
            "packaged wave-64 ledger is invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise LegacyXGBoostNativeWave64Error(
            "packaged wave-64 ledger must be an object"
        )
    document = cast(dict[str, Any], parsed)
    reduced = {
        key: value
        for key, value in document.items()
        if key != "ledger_content_sha256"
    }
    if (
        document.get("ledger_schema_version") != LEDGER_SCHEMA_VERSION
        or document.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
        or hashlib.sha256(_canonical_bytes(reduced)).hexdigest()
        != LEDGER_CONTENT_SHA256
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("legacy_method_id") != METHOD_ID
        or document.get("source_sha256") != SOURCE_SHA256
        or document.get("causal_protocol") != CAUSAL_PROTOCOL
        or document.get("causal_eligibility_rule")
        != CAUSAL_ELIGIBILITY_RULE
        or hashlib.sha256(
            _canonical_bytes(document.get("tickets"))
        ).hexdigest()
        != TICKET_SEQUENCE_SHA256
        or hashlib.sha256(
            _canonical_bytes(
                document.get("selected_probabilities_by_target")
            )
        ).hexdigest()
        != PROBABILITY_SEQUENCE_SHA256
    ):
        raise LegacyXGBoostNativeWave64Error(
            "packaged wave-64 ledger identity changed"
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
    probabilities_raw = cast(
        list[object],
        document.get("selected_probabilities_by_target", []),
    )
    confidences_raw = cast(
        list[object],
        document.get("confidence_by_target", []),
    )
    reasons_raw = cast(
        list[object],
        document.get("closed_reason", []),
    )
    if not (
        len(targets_raw)
        == len(contexts_raw)
        == len(counts_raw)
        == len(tickets_raw)
        == len(probabilities_raw)
        == len(confidences_raw)
        == len(reasons_raw)
        == 2149
    ):
        raise LegacyXGBoostNativeWave64Error(
            "packaged wave-64 coverage changed"
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
        raise LegacyXGBoostNativeWave64Error(
            "packaged wave-64 target identity changed"
        )
    portfolios: list[tuple[Ticket, ...] | None] = []
    probabilities: list[tuple[float, ...] | None] = []
    confidences: list[float | None] = []
    reasons: list[str | None] = []
    for index, (portfolio_raw, selected_raw, confidence, reason) in enumerate(
        zip(
            tickets_raw,
            probabilities_raw,
            confidences_raw,
            reasons_raw,
            strict=True,
        )
    ):
        if index < 15:
            if (
                portfolio_raw is not None
                or selected_raw is not None
                or confidence is not None
                or reason != CLOSED_REASON
            ):
                raise LegacyXGBoostNativeWave64Error(
                    "packaged wave-64 closed boundary changed"
                )
            portfolios.append(None)
            probabilities.append(None)
            confidences.append(None)
            reasons.append(CLOSED_REASON)
            continue
        if (
            not isinstance(portfolio_raw, list)
            or len(cast(list[object], portfolio_raw)) != 1
            or not isinstance(selected_raw, list)
            or len(cast(list[object], selected_raw)) != 6
            or any(
                type(value) is not float
                for value in cast(list[object], selected_raw)
            )
            or type(confidence) is not float
            or reason is not None
        ):
            raise LegacyXGBoostNativeWave64Error(
                "packaged wave-64 executable row changed"
            )
        portfolio = tuple(
            _ticket(ticket)
            for ticket in cast(list[object], portfolio_raw)
        )
        portfolios.append(portfolio)
        probabilities.append(
            tuple(cast(list[float], selected_raw))
        )
        confidences.append(confidence)
        reasons.append(None)
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
        probabilities=tuple(probabilities),
        confidences=tuple(confidences),
        closed_reason=tuple(reasons),
    )


def load_legacy_xgboost_native_wave64_ledger_for_verification() -> _Ledger:
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


def generate_legacy_xgboost_native_wave64_portfolio(
    request: LegacyXGBoostNativeWave64Request,
) -> LegacyXGBoostNativeWave64Result:
    """Replay one causal frozen XGBoost native ticket."""

    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.target_draw_date) is not date
        or type(request.dataset_sha256) is not str or not request.dataset_sha256
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
    ):
        raise LegacyXGBoostNativeWave64Error(
            "invalid wave-64 request identity"
        )
    ledger = _load_ledger()
    target_index = ledger.target_index.get(request.target_draw_number)
    if target_index is None:
        raise LegacyXGBoostNativeWave64SourceError(
            "TARGET_OUTSIDE_FROZEN_WAVE64_TICKET_LEDGER"
        )
    context_sha256 = _context_sha256(request.history)
    if context_sha256 != ledger.context_sha256[target_index]:
        raise LegacyXGBoostNativeWave64SourceError(
            "FROZEN_WAVE64_FULL_PREFIX_CONTEXT_MISMATCH"
        )
    tickets = ledger.tickets[target_index]
    if tickets is None:
        raise LegacyXGBoostNativeWave64SourceError(
            ledger.closed_reason[target_index]
            or "FROZEN_WAVE64_CLOSED_WITHOUT_REASON"
        )
    selected_probabilities = ledger.probabilities[target_index]
    confidence = ledger.confidences[target_index]
    if (
        selected_probabilities is None
        or confidence is None
        or len(request.history) < 15
        or len(tickets) != 1
    ):
        raise LegacyXGBoostNativeWave64Error(
            "executable wave-64 row lacks causal model state"
        )
    seed_material = (
        "xgboost=2.0.2;random_state=None;subsample=1;"
        "colsample_bytree=1;n_jobs=-1;repeat_thread_parity=PASS"
    )
    return LegacyXGBoostNativeWave64Result(
        tickets=tickets,
        metadata=LegacyXGBoostNativeWave64Metadata(
            protocol=SOURCE_NATIVE_WAVE64_PROTOCOL,
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
            determinism_protocol=DETERMINISM_PROTOCOL,
            randomness_used=False,
            source_random_state_explicit=False,
            repeatability_parity_passed=True,
            thread_count_parity_passed=True,
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="OLDEST_FIRST",
            source_history_input_draw_count=(
                ledger.history_input_draw_count[target_index]
            ),
            source_history_input_upper_bound=1000,
            context_draw_count=len(request.history),
            context_numbers_sha256=context_sha256,
            model_label_count=49,
            estimators_per_label=50,
            model_max_depth=3,
            source_candidate_k_values=(49,),
            candidate_k=None,
            native_ticket_count=1,
            native_ticket_count_semantics=NATIVE_TICKET_SEMANTICS,
            native_ticket_order=NATIVE_TICKET_ORDER,
            native_duplicate_ticket_count=0,
            combination_count=None,
            local_configuration_count=1,
            selected_probabilities=selected_probabilities,
            confidence=confidence,
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
    "CLOSED_REASON",
    "CONTEXT_POLICY",
    "DEFAULT_SOURCE_NATIVE_WAVE64_USER_SEED",
    "DETERMINISM_PROTOCOL",
    "FROZEN_SOURCE_COMMIT",
    "LEDGER_CONTENT_SHA256",
    "LEDGER_FILE_SHA256",
    "LEDGER_RESOURCE_NAME",
    "LEDGER_SCHEMA_VERSION",
    "METHOD_ID",
    "MODEL_CANDIDATE_K",
    "NATIVE_TICKET_ORDER",
    "NATIVE_TICKET_SEMANTICS",
    "PINNED_DATASET_SHA256",
    "PROBABILITY_SEQUENCE_SHA256",
    "SOURCE_NATIVE_WAVE64_PROTOCOL",
    "SOURCE_REFERENCE_RUNTIME",
    "SOURCE_SHA256",
    "TICKET_SEQUENCE_SHA256",
    "LegacyXGBoostNativeWave64Error",
    "LegacyXGBoostNativeWave64Metadata",
    "LegacyXGBoostNativeWave64Request",
    "LegacyXGBoostNativeWave64Result",
    "LegacyXGBoostNativeWave64SourceError",
    "generate_legacy_xgboost_native_wave64_portfolio",
    "load_legacy_xgboost_native_wave64_ledger_for_verification",
]
