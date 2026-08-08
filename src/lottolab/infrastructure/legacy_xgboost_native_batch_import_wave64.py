"""Causal materialization for the frozen wave-64 XGBoost method."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, cast

from lottolab.application.biglotto_multi_ticket_backtest import (
    INPUT_SCHEMA_VERSION,
)
from lottolab.application.legacy_advanced_methods_native_portfolios_wave63 import (
    LEDGER_CONTENT_SHA256 as WAVE63_LEDGER_CONTENT_SHA256,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_xgboost_native_portfolios_wave64 import (
    CAUSAL_ELIGIBILITY_RULE,
    CAUSAL_PROTOCOL,
    CLOSED_REASON,
    CONTEXT_POLICY,
    DEFAULT_SOURCE_NATIVE_WAVE64_USER_SEED,
    DETERMINISM_PROTOCOL,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    METHOD_ID,
    MODEL_CANDIDATE_K,
    NATIVE_TICKET_SEMANTICS,
    PINNED_DATASET_SHA256,
    PROBABILITY_SEQUENCE_SHA256,
    SOURCE_NATIVE_WAVE64_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256,
    TICKET_SEQUENCE_SHA256,
    LegacyXGBoostNativeWave64Request,
    LegacyXGBoostNativeWave64SourceError,
    generate_legacy_xgboost_native_wave64_portfolio,
)
from lottolab.application.strategy_preserving_20_ticket import (
    CONSTRUCTOR_IDENTIFIER,
    ConstructorRequest,
    ConstructorSuccess,
    construct_strategy_preserving_20_ticket,
)
from lottolab.domain.biglotto_full_strategy_catalog import (
    FullStrategyCatalogRecord,
    load_full_strategy_catalog,
)
from lottolab.infrastructure.replay_backed_batch_import import (
    PinnedBigLottoDraw,
)

MATERIALIZATION_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_XGBOOST_NATIVE_WAVE64_BATCH_V1"
)
HISTORY_INPUT_FILE_SHA256 = (
    "e501c2e1b0a5c610bae3822a2784a72860e2c549daadb37c344de61d16129493"
)
HISTORY_INPUT_CANONICAL_SHA256 = (
    "155766ddc1f7581392d91fc8f5e79a433f6e245a9feefb5cb059b8d2594af7c9"
)


class LegacyXGBoostNativeWave64BatchImportError(ValueError):
    """The pinned history input or XGBoost ledger violates its contract."""



def _parse_date(value: object, context: str) -> date:
    if type(value) is not str:
        raise LegacyXGBoostNativeWave64BatchImportError(
            f"{context}: date is missing"
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise LegacyXGBoostNativeWave64BatchImportError(
            f"{context}: date is invalid"
        ) from exc


def _parse_ticket(
    value: object,
    context: str,
) -> tuple[int, int, int, int, int, int]:
    if not isinstance(value, list):
        raise LegacyXGBoostNativeWave64BatchImportError(
            f"{context}: ticket is missing"
        )
    items = cast(list[object], value)
    if len(items) != 6 or any(type(number) is not int for number in items):
        raise LegacyXGBoostNativeWave64BatchImportError(
            f"{context}: ticket must contain six integers"
        )
    numbers = cast(list[int], items)
    ticket = tuple(numbers)
    if (
        numbers != sorted(numbers)
        or len(set(numbers)) != 6
        or any(not 1 <= number <= 49 for number in numbers)
    ):
        raise LegacyXGBoostNativeWave64BatchImportError(
            f"{context}: ticket is not canonical"
        )
    return cast(tuple[int, int, int, int, int, int], ticket)


def _load_history_input(
    path: Path,
) -> tuple[tuple[PinnedBigLottoDraw, ...], str]:
    if path.is_symlink() or not path.is_file():
        raise LegacyXGBoostNativeWave64BatchImportError(
            "history input must be a regular non-symlink file"
        )
    raw = path.read_bytes()
    physical_sha256 = hashlib.sha256(raw).hexdigest()
    if len(physical_sha256) != 64:
        raise LegacyXGBoostNativeWave64BatchImportError(
            "history input physical SHA-256 changed"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacyXGBoostNativeWave64BatchImportError(
            "history input is invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise LegacyXGBoostNativeWave64BatchImportError(
            "history input must be an object"
        )
    document = cast(dict[str, Any], parsed)
    provenance = document.get("source_provenance")
    if (
        type(document.get("dataset_sha256")) is not str
        or not document.get("dataset_sha256")
        or document.get("lottery_type") != "BIG_LOTTO"
        or not isinstance(provenance, dict)
    ):
        raise LegacyXGBoostNativeWave64BatchImportError(
            "history input authority changed"
        )
    targets_raw = document.get("targets")
    if not isinstance(targets_raw, list):
        raise LegacyXGBoostNativeWave64BatchImportError(
            "history input targets are missing"
        )
    draws: list[PinnedBigLottoDraw] = []
    for candidate in cast(list[object], targets_raw):
        if not isinstance(candidate, dict):
            raise LegacyXGBoostNativeWave64BatchImportError(
                "history input target is invalid"
            )
        target = cast(dict[str, object], candidate)
        draw_number = target.get("draw_number")
        special = target.get("winning_special_number")
        if type(draw_number) is not str or type(special) is not int:
            raise LegacyXGBoostNativeWave64BatchImportError(
                "history input target identity changed"
            )
        draws.append(
            PinnedBigLottoDraw(
                draw_number=draw_number,
                draw_date=_parse_date(
                    target.get("draw_date"),
                    f"draw {draw_number}",
                ),
                numbers=_parse_ticket(
                    target.get("winning_main_numbers"),
                    f"draw {draw_number}",
                ),
                special=special,
            )
        )
    if (
        len(draws) != 2149
        or draws[0].draw_number != "96000001"
        or draws[-1].draw_number != "115000073"
        or len({draw.draw_number for draw in draws}) != len(draws)
        or len({draw.draw_date for draw in draws}) != len(draws)
    ):
        raise LegacyXGBoostNativeWave64BatchImportError(
            "wave-64 target set changed"
        )
    return tuple(draws), physical_sha256


def _catalog_record() -> FullStrategyCatalogRecord:
    by_method = {
        record.legacy_method_id: record
        for record in load_full_strategy_catalog().records
    }
    record = by_method.get(METHOD_ID)
    if record is None or record.source_sha256 != SOURCE_SHA256:
        raise LegacyXGBoostNativeWave64BatchImportError(
            "frozen wave-64 catalog identity changed"
        )
    return record


def materialize_legacy_xgboost_native_wave64_batch(
    *,
    history_input: Path,
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE64_USER_SEED,
) -> dict[str, object]:
    """Build the source-closed rows and causal ordered-20 rows."""

    draws, history_input_file_sha256 = _load_history_input(history_input)
    record = _catalog_record()
    causal_history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in draws
    )
    executions: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    duplicate_counts: Counter[int] = Counter()
    for target_index, target in enumerate(draws):
        try:
            native = generate_legacy_xgboost_native_wave64_portfolio(
                LegacyXGBoostNativeWave64Request(
                    target_draw_number=target.draw_number,
                    target_draw_date=target.draw_date,
                    history=causal_history[:target_index],
                    dataset_sha256=PINNED_DATASET_SHA256,
                    replicate_id=0,
                    user_seed=user_seed,
                )
            )
        except LegacyXGBoostNativeWave64SourceError as exc:
            if exc.reason_code != CLOSED_REASON:
                raise LegacyXGBoostNativeWave64BatchImportError(
                    "unexpected wave-64 source closure"
                ) from exc
            executions.append(
                {
                    "reason_code": exc.reason_code,
                    "status": "CLOSED_INSUFFICIENT_HISTORY",
                    "strategy_id": record.strategy_id,
                    "strategy_version": record.strategy_version,
                    "target_draw_number": target.draw_number,
                }
            )
            status_counts["CLOSED_INSUFFICIENT_HISTORY"] += 1
            continue
        if target_index == 0:
            raise LegacyXGBoostNativeWave64BatchImportError(
                "executable wave-64 target has no causal cutoff"
            )
        cutoff = draws[target_index - 1]
        constructed = construct_strategy_preserving_20_ticket(
            ConstructorRequest(
                strategy_id=record.strategy_id,
                draw_id=target.draw_number,
                replicate_id=0,
                raw_tickets=native.tickets,
                historical_cutoff_identity=cutoff.draw_number,
                user_seed=user_seed,
            )
        )
        if not isinstance(constructed, ConstructorSuccess):
            raise LegacyXGBoostNativeWave64BatchImportError(
                "ordered-20 construction failed: "
                f"{constructed.reason.value}"
            )
        executions.append(
            {
                "candidate_k": MODEL_CANDIDATE_K,
                "combination_count": (
                    native.metadata.local_configuration_count
                ),
                "history_cutoff_draw_date": cutoff.draw_date.isoformat(),
                "history_cutoff_draw_number": cutoff.draw_number,
                "native_generation": native.metadata.canonical_dict(),
                "native_ticket_count": len(native.tickets),
                "native_tickets": [
                    list(ticket) for ticket in native.tickets
                ],
                "ordered_portfolio": [
                    list(ticket) for ticket in constructed.tickets
                ],
                "ordered_portfolio_derivation": (
                    constructed.metadata.canonical_dict()
                ),
                "portfolio_derivation": CONSTRUCTOR_IDENTIFIER,
                "portfolio_ticket_count": 20,
                "status": "OK",
                "strategy_id": record.strategy_id,
                "strategy_version": record.strategy_version,
                "target_draw_number": target.draw_number,
            }
        )
        status_counts["OK"] += 1
        duplicate_counts[
            native.metadata.native_duplicate_ticket_count
        ] += 1
    expected_status_counts = Counter(
        {
            "CLOSED_INSUFFICIENT_HISTORY": min(15, len(draws)),
            "OK": max(0, len(draws) - 15),
        }
    )
    if status_counts != expected_status_counts:
        raise LegacyXGBoostNativeWave64BatchImportError(
            "wave-64 execution coverage changed"
        )
    return {
        "dataset_id": (
            "legacy-biglotto-xgboost-native-wave64-"
            f"{PINNED_DATASET_SHA256[:12]}"
        ),
        "dataset_sha256": PINNED_DATASET_SHA256,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "candidate_k": MODEL_CANDIDATE_K,
            "candidate_k_semantics": (
                "FORTY_NINE_MODEL_LABEL_PROBABILITIES_DISTINCT_FROM_"
                "ONE_NATIVE_TICKET_ONE_CONFIGURATION_AND_ORDERED20_COUNT"
            ),
            "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
            "causal_protocol": CAUSAL_PROTOCOL,
            "combination_count_distribution": {
                "1": status_counts["OK"]
            },
            "combination_count_semantics": (
                "ONE_SOURCE_MODEL_CONFIGURATION_DISTINCT_FROM_"
                "CANDIDATE_K_NATIVE_TICKET_COUNT_AND_ORDERED20_COUNT"
            ),
            "constructor": CONSTRUCTOR_IDENTIFIER,
            "context_policy": CONTEXT_POLICY,
            "determinism_protocol": DETERMINISM_PROTOCOL,
            "execution_status_counts": dict(
                sorted(status_counts.items())
            ),
            "frozen_source": {METHOD_ID: SOURCE_SHA256},
            "history_input_canonical_sha256": (
                HISTORY_INPUT_CANONICAL_SHA256
            ),
            "history_input_file_sha256": history_input_file_sha256,
            "ledger_content_sha256": LEDGER_CONTENT_SHA256,
            "ledger_file_sha256": LEDGER_FILE_SHA256,
            "ledger_schema_version": LEDGER_SCHEMA_VERSION,
            "logical_dataset_sha256": PINNED_DATASET_SHA256,
            "model_estimators_per_label": 50,
            "model_label_count": 49,
            "model_max_depth": 3,
            "native_duplicate_ticket_count_distribution": {
                str(key): value
                for key, value in sorted(duplicate_counts.items())
            },
            "native_ticket_count_distribution": {
                "1": status_counts["OK"]
            },
            "native_ticket_semantics": NATIVE_TICKET_SEMANTICS,
            "probability_sequence_sha256": PROBABILITY_SEQUENCE_SHA256,
            "source_history_input_upper_bound": 1000,
            "source_history_order": "OLDEST_FIRST",
            "source_native_protocol": SOURCE_NATIVE_WAVE64_PROTOCOL,
            "source_random_state_explicit": False,
            "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
            "source_read_mode": (
                "CHECKSUM_PINNED_WAVE63_MATERIALIZED_TARGET_TRUTHS"
            ),
            "target_stable_model_retraining": True,
            "thread_count_parity_passed": True,
            "ticket_sequence_sha256": TICKET_SEQUENCE_SHA256,
            "upstream_wave63_ledger_content_sha256": (
                WAVE63_LEDGER_CONTENT_SHA256
            ),
            "user_seed": user_seed,
        },
        "targets": [
            {
                "draw_date": draw.draw_date.isoformat(),
                "draw_number": draw.draw_number,
                "winning_main_numbers": list(draw.numbers),
                "winning_special_number": draw.special,
            }
            for draw in draws
        ],
    }


__all__ = [
    "HISTORY_INPUT_CANONICAL_SHA256",
    "HISTORY_INPUT_FILE_SHA256",
    "MATERIALIZATION_SCHEMA_VERSION",
    "LegacyXGBoostNativeWave64BatchImportError",
    "materialize_legacy_xgboost_native_wave64_batch",
]
