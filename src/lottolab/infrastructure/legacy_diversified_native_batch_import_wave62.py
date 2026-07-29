"""Causal materialization for wave-62 diversified source portfolios."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from lottolab.application.biglotto_multi_ticket_backtest import (
    INPUT_SCHEMA_VERSION,
)
from lottolab.application.legacy_diversified_native_portfolios_wave62 import (
    CAUSAL_ELIGIBILITY_RULE,
    CAUSAL_PROTOCOL,
    CONTEXT_POLICY,
    DEFAULT_SOURCE_NATIVE_WAVE62_USER_SEED,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    MODEL_CANDIDATE_K,
    NATIVE_TICKET_ORDER_BY_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_METHOD,
    PINNED_DATASET_SHA256,
    RANDOM_PROTOCOL_BY_METHOD,
    SOURCE_CANDIDATE_K_VALUES_BY_METHOD,
    SOURCE_CLOSED_RESULT_HORIZONS_BY_METHOD,
    SOURCE_NATIVE_WAVE62_PROTOCOL,
    SOURCE_RANDOM_BASELINE_EXCLUDED_BY_METHOD,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_METHOD,
    SUPPORTED_METHODS,
    LegacyDiversifiedNativeWave62Request,
    LegacyDiversifiedNativeWave62SourceError,
    generate_legacy_diversified_native_wave62_portfolio,
    load_legacy_diversified_native_wave62_ledger_for_verification,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
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
    PinnedBigLottoHistory,
    ReplayBatchImportError,
    load_pinned_biglotto_history,
)

MATERIALIZATION_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_DIVERSIFIED_NATIVE_WAVE62_BATCH_V1"
)


class LegacyDiversifiedNativeWave62BatchImportError(ValueError):
    """The pinned dataset or wave-62 ledger violates the batch contract."""


def _validate_logical_dataset_identity(
    pinned_history: PinnedBigLottoHistory,
    causal_history: tuple[LegacyHistoryDraw, ...],
) -> str:
    physical_sha256 = pinned_history.database_sha256_before
    if physical_sha256 == PINNED_DATASET_SHA256:
        return PINNED_DATASET_SHA256
    ledger = (
        load_legacy_diversified_native_wave62_ledger_for_verification()
    )
    if (
        len(pinned_history.draws) != 2149
        or tuple(
            draw.draw_number for draw in pinned_history.draws
        )
        != ledger.targets
        or pinned_history.database_sha256_after != physical_sha256
    ):
        raise LegacyDiversifiedNativeWave62BatchImportError(
            "regeneration database leaves the pinned logical target sequence"
        )
    contexts = tuple(
        hashlib.sha256(
            json.dumps(
                [list(draw.numbers) for draw in causal_history[:index]],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        for index in range(len(causal_history))
    )
    if contexts != ledger.context_sha256:
        raise LegacyDiversifiedNativeWave62BatchImportError(
            "regeneration database leaves the pinned logical history"
        )
    return PINNED_DATASET_SHA256


def _catalog_records() -> dict[str, FullStrategyCatalogRecord]:
    by_method = {
        record.legacy_method_id: record
        for record in load_full_strategy_catalog().records
    }
    records: dict[str, FullStrategyCatalogRecord] = {}
    for method_id in SUPPORTED_METHODS:
        record = by_method.get(method_id)
        if (
            record is None
            or record.source_sha256
            != SOURCE_SHA256_BY_METHOD[method_id]
        ):
            raise LegacyDiversifiedNativeWave62BatchImportError(
                "frozen wave-62 catalog identity changed"
            )
        records[method_id] = record
    return records


def _closed_status(reason_code: str) -> str:
    if reason_code == (
        "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
    ):
        return "CLOSED_INSUFFICIENT_HISTORY"
    if reason_code.startswith("FROZEN_SOURCE_EXECUTION_ERROR:"):
        return "CLOSED_EXECUTION_ERROR"
    return "CLOSED_REJECTED"


def materialize_legacy_diversified_native_wave62_batch(
    *,
    database: Path,
    expected_database_sha256: str,
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE62_USER_SEED,
) -> dict[str, object]:
    """Build causal ordered-20 and explicit source-closed rows."""

    try:
        pinned_history = load_pinned_biglotto_history(
            database=database,
            expected_database_sha256=expected_database_sha256,
        )
    except ReplayBatchImportError as exc:
        raise LegacyDiversifiedNativeWave62BatchImportError(
            str(exc)
        ) from exc
    records = _catalog_records()
    causal_history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in pinned_history.draws
    )
    logical_dataset_sha256 = _validate_logical_dataset_identity(
        pinned_history,
        causal_history,
    )
    executions: list[dict[str, object]] = []
    status_counts_by_method: dict[str, Counter[str]] = {
        method_id: Counter() for method_id in SUPPORTED_METHODS
    }
    native_counts_by_method: dict[str, Counter[int]] = {
        method_id: Counter() for method_id in SUPPORTED_METHODS
    }
    configuration_counts_by_method: dict[str, Counter[int]] = {
        method_id: Counter() for method_id in SUPPORTED_METHODS
    }
    duplicate_counts_by_method: dict[str, Counter[int]] = {
        method_id: Counter() for method_id in SUPPORTED_METHODS
    }
    for method_id in SUPPORTED_METHODS:
        record = records[method_id]
        for target_index, target in enumerate(pinned_history.draws):
            try:
                native = (
                    generate_legacy_diversified_native_wave62_portfolio(
                        LegacyDiversifiedNativeWave62Request(
                            legacy_method_id=method_id,
                            target_draw_number=target.draw_number,
                            target_draw_date=target.draw_date,
                            history=causal_history[:target_index],
                            dataset_sha256=logical_dataset_sha256,
                            replicate_id=0,
                            user_seed=user_seed,
                        )
                    )
                )
            except LegacyDiversifiedNativeWave62SourceError as exc:
                status = _closed_status(exc.reason_code)
                executions.append(
                    {
                        "reason_code": exc.reason_code,
                        "status": status,
                        "strategy_id": record.strategy_id,
                        "strategy_version": record.strategy_version,
                        "target_draw_number": target.draw_number,
                    }
                )
                status_counts_by_method[method_id][status] += 1
                continue
            if target_index == 0:
                raise LegacyDiversifiedNativeWave62BatchImportError(
                    "executable wave-62 target has no causal cutoff"
                )
            cutoff = pinned_history.draws[target_index - 1]
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
                raise LegacyDiversifiedNativeWave62BatchImportError(
                    "ordered-20 construction failed: "
                    f"{constructed.reason.value}"
                )
            executions.append(
                {
                    "candidate_k": MODEL_CANDIDATE_K,
                    "combination_count": (
                        native.metadata.local_configuration_count
                    ),
                    "history_cutoff_draw_date": (
                        cutoff.draw_date.isoformat()
                    ),
                    "history_cutoff_draw_number": cutoff.draw_number,
                    "native_generation": (
                        native.metadata.canonical_dict()
                    ),
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
            status_counts_by_method[method_id]["OK"] += 1
            native_counts_by_method[method_id][
                len(native.tickets)
            ] += 1
            configuration_counts_by_method[method_id][
                native.metadata.local_configuration_count
            ] += 1
            duplicate_counts_by_method[method_id][
                native.metadata.native_duplicate_ticket_count
            ] += 1
    return {
        "dataset_id": (
            f"legacy-biglotto-diversified-native-wave62-"
            f"{logical_dataset_sha256[:12]}"
        ),
        "dataset_sha256": logical_dataset_sha256,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "candidate_k": MODEL_CANDIDATE_K,
            "candidate_k_semantics": (
                "FULL_49_LEGAL_NUMBER_DOMAIN_FOR_ORDERED20_INPUT_"
                "DISTINCT_FROM_SOURCE_CANDIDATE_POOLS_NATIVE_TICKET_"
                "COUNT_LOCAL_CONFIGURATION_COUNT_AND_ORDERED20_COUNT"
            ),
            "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
            "causal_protocol": CAUSAL_PROTOCOL,
            "combination_count_distribution_by_method": {
                method_id: dict(
                    sorted(
                        configuration_counts_by_method[
                            method_id
                        ].items()
                    )
                )
                for method_id in SUPPORTED_METHODS
            },
            "combination_count_semantics": (
                "EXECUTED_SOURCE_CONFIGURATION_BLOCK_COUNT_DISTINCT_"
                "FROM_CANDIDATE_K_NATIVE_TICKET_COUNT_AND_ORDERED20_COUNT"
            ),
            "constructor": CONSTRUCTOR_IDENTIFIER,
            "context_policy": CONTEXT_POLICY,
            "database_sha256_after": (
                pinned_history.database_sha256_after
            ),
            "database_sha256_before": (
                pinned_history.database_sha256_before
            ),
            "execution_status_counts_by_method": {
                method_id: dict(
                    sorted(status_counts_by_method[method_id].items())
                )
                for method_id in SUPPORTED_METHODS
            },
            "frozen_source": dict(SOURCE_SHA256_BY_METHOD),
            "ledger_content_sha256": LEDGER_CONTENT_SHA256,
            "ledger_file_sha256": LEDGER_FILE_SHA256,
            "ledger_schema_version": LEDGER_SCHEMA_VERSION,
            "logical_dataset_sha256": logical_dataset_sha256,
            "native_duplicate_ticket_count_distribution_by_method": {
                method_id: dict(
                    sorted(
                        duplicate_counts_by_method[
                            method_id
                        ].items()
                    )
                )
                for method_id in SUPPORTED_METHODS
            },
            "native_ticket_count_distribution_by_method": {
                method_id: dict(
                    sorted(
                        native_counts_by_method[method_id].items()
                    )
                )
                for method_id in SUPPORTED_METHODS
            },
            "native_ticket_order_by_method": dict(
                NATIVE_TICKET_ORDER_BY_METHOD
            ),
            "native_ticket_semantics_by_method": dict(
                NATIVE_TICKET_SEMANTICS_BY_METHOD
            ),
            "random_protocol_by_method": dict(
                RANDOM_PROTOCOL_BY_METHOD
            ),
            "replay_truth_supplemented_draw_count": (
                pinned_history.replay_truth_supplemented_draw_count
            ),
            "source_candidate_k_values_by_method": {
                method_id: list(
                    SOURCE_CANDIDATE_K_VALUES_BY_METHOD[method_id]
                )
                for method_id in SUPPORTED_METHODS
            },
            "source_closed_result_horizons_by_method": {
                method_id: list(
                    SOURCE_CLOSED_RESULT_HORIZONS_BY_METHOD[
                        method_id
                    ]
                )
                for method_id in SUPPORTED_METHODS
            },
            "source_history_order": (
                "RECENT_FIRST_CALL_THEN_SOURCE_DATE_ASC_SORT"
            ),
            "source_native_protocol": SOURCE_NATIVE_WAVE62_PROTOCOL,
            "source_random_baseline_excluded_by_method": dict(
                SOURCE_RANDOM_BASELINE_EXCLUDED_BY_METHOD
            ),
            "source_read_mode": (
                "sqlite-mode=ro,immutable=1,query_only=ON"
            ),
            "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
            "user_seed": user_seed,
        },
        "targets": [
            {
                "draw_date": draw.draw_date.isoformat(),
                "draw_number": draw.draw_number,
                "winning_main_numbers": list(draw.numbers),
                "winning_special_number": draw.special,
            }
            for draw in pinned_history.draws
        ],
    }


__all__ = [
    "MATERIALIZATION_SCHEMA_VERSION",
    "LegacyDiversifiedNativeWave62BatchImportError",
    "materialize_legacy_diversified_native_wave62_batch",
]
