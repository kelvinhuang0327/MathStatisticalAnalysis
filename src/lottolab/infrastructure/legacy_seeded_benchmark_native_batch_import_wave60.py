"""Causal materialization for the wave-60 seeded benchmark selectors."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from lottolab.application.biglotto_multi_ticket_backtest import (
    INPUT_SCHEMA_VERSION,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_seeded_benchmark_native_portfolios_wave60 import (
    CAUSAL_ELIGIBILITY_RULE,
    CAUSAL_PROTOCOL,
    CONTEXT_POLICY,
    DEFAULT_SOURCE_NATIVE_WAVE60_USER_SEED,
    IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE60_METHOD,
    INSUFFICIENT_HISTORY_REASON,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    LOCAL_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD,
    MINIMUM_HISTORY_DRAWS,
    MODEL_CANDIDATE_K,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE60_METHOD,
    PINNED_DATASET_SHA256,
    SOURCE_NATIVE_WAVE60_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE60_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS,
    LegacySeededBenchmarkNativeWave60Request,
    generate_legacy_seeded_benchmark_native_wave60_portfolio,
    load_legacy_seeded_benchmark_native_wave60_ledger_for_verification,
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
    "BIG_LOTTO_LEGACY_SEEDED_BENCHMARK_NATIVE_WAVE60_BATCH_V1"
)


class LegacySeededBenchmarkNativeWave60BatchImportError(ValueError):
    """The pinned dataset or wave-60 ledger violates the batch contract."""


def _validate_logical_dataset_identity(
    pinned_history: PinnedBigLottoHistory,
    causal_history: tuple[LegacyHistoryDraw, ...],
) -> str:
    physical_sha256 = pinned_history.database_sha256_before
    if physical_sha256 == PINNED_DATASET_SHA256:
        return PINNED_DATASET_SHA256
    ledger = (
        load_legacy_seeded_benchmark_native_wave60_ledger_for_verification()
    )
    if (
        len(pinned_history.draws) != 2149
        or tuple(
            draw.draw_number for draw in pinned_history.draws
        )
        != ledger.targets
        or pinned_history.database_sha256_after != physical_sha256
    ):
        raise LegacySeededBenchmarkNativeWave60BatchImportError(
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
        raise LegacySeededBenchmarkNativeWave60BatchImportError(
            "regeneration database leaves the pinned logical history"
        )
    return PINNED_DATASET_SHA256


def _catalog_records() -> dict[str, FullStrategyCatalogRecord]:
    by_method = {
        record.legacy_method_id: record
        for record in load_full_strategy_catalog().records
    }
    records: dict[str, FullStrategyCatalogRecord] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS:
        record = by_method.get(method_id)
        if (
            record is None
            or record.source_sha256
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE60_METHOD[method_id]
        ):
            raise LegacySeededBenchmarkNativeWave60BatchImportError(
                "frozen wave-60 catalog identity changed"
            )
        records[method_id] = record
    return records


def materialize_legacy_seeded_benchmark_native_wave60_batch(
    *,
    database: Path,
    expected_database_sha256: str,
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE60_USER_SEED,
) -> dict[str, object]:
    """Build ordered-20 input with explicit source-minimum closures."""

    try:
        pinned_history = load_pinned_biglotto_history(
            database=database,
            expected_database_sha256=expected_database_sha256,
            require_replay_authority=False,
        )
    except ReplayBatchImportError as exc:
        raise LegacySeededBenchmarkNativeWave60BatchImportError(
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
    aggregate_status_counts: Counter[str] = Counter()
    status_counts_by_method: dict[str, dict[str, int]] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS:
        record = records[method_id]
        method_status_counts: Counter[str] = Counter()
        minimum = MINIMUM_HISTORY_DRAWS
        for target_index, target in enumerate(pinned_history.draws):
            if target_index < minimum:
                executions.append(
                    {
                        "reason_code": INSUFFICIENT_HISTORY_REASON,
                        "status": "CLOSED_INSUFFICIENT_HISTORY",
                        "strategy_id": record.strategy_id,
                        "strategy_version": record.strategy_version,
                        "target_draw_number": target.draw_number,
                    }
                )
                method_status_counts["CLOSED_INSUFFICIENT_HISTORY"] += 1
                aggregate_status_counts["CLOSED_INSUFFICIENT_HISTORY"] += 1
                continue
            cutoff = pinned_history.draws[target_index - 1]
            native = (
                generate_legacy_seeded_benchmark_native_wave60_portfolio(
                    LegacySeededBenchmarkNativeWave60Request(
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
                raise LegacySeededBenchmarkNativeWave60BatchImportError(
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
            method_status_counts["OK"] += 1
            aggregate_status_counts["OK"] += 1
        status_counts_by_method[method_id] = dict(
            sorted(method_status_counts.items())
        )
    return {
        "dataset_id": (
            f"legacy-biglotto-seeded-benchmark-native-wave60-"
            f"{logical_dataset_sha256[:12]}"
        ),
        "dataset_sha256": logical_dataset_sha256,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "candidate_k": {
                method_id: MODEL_CANDIDATE_K
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS
            },
            "candidate_k_semantics": (
                "FULL_49_LEGAL_NUMBER_DOMAIN_FOR_ORDERED20_INPUT_DISTINCT_"
                "FROM_SOURCE_CANDIDATE_POOLS_NATIVE_TICKET_COUNT_LOCAL_"
                "CONFIGURATION_COUNT_AND_ORDERED20_COUNT"
            ),
            "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
            "causal_protocol": CAUSAL_PROTOCOL,
            "combination_count": {
                method_id: (
                    LOCAL_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD[
                        method_id
                    ]
                )
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS
            },
            "combination_count_semantics": (
                "DECLARED_BIG_LOTTO_LOCAL_CONFIGURATION_COUNT_DISTINCT_"
                "FROM_CANDIDATE_K_NATIVE_TICKET_COUNT_AND_ORDERED20_COUNT"
            ),
            "constructor": CONSTRUCTOR_IDENTIFIER,
            "context_policy": CONTEXT_POLICY,
            "database_sha256_after": pinned_history.database_sha256_after,
            "database_sha256_before": (
                pinned_history.database_sha256_before
            ),
            "execution_status_counts": dict(
                sorted(aggregate_status_counts.items())
            ),
            "execution_status_counts_by_method": status_counts_by_method,
            "frozen_sources": dict(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE60_METHOD
            ),
            "imported_comparators_excluded": dict(
                IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE60_METHOD
            ),
            "ledger_content_sha256": LEDGER_CONTENT_SHA256,
            "ledger_file_sha256": LEDGER_FILE_SHA256,
            "ledger_schema_version": LEDGER_SCHEMA_VERSION,
            "local_source_configurations": dict(
                LOCAL_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD
            ),
            "logical_dataset_sha256": logical_dataset_sha256,
            "logical_history_anchor": (
                "CHECKSUMMED_WAVE60_ALL_TARGET_FULL_PREFIX_CONTEXT_LEDGER"
            ),
            "minimum_history_draws": dict(
                (
                    method_id,
                    MINIMUM_HISTORY_DRAWS,
                )
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS
            ),
            "native_ticket_count": dict(
                NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE60_METHOD
            ),
            "native_ticket_semantics": dict(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE60_METHOD
            ),
            "random_protocols": dict(
                (
                    method_id,
                    "PYTHON_AND_NUMPY_SEED42_RESET_PER_TARGET",
                )
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS
            ),
            "replay_truth_supplemented_draw_count": (
                pinned_history.replay_truth_supplemented_draw_count
            ),
            "source_candidate_k_values": {
                method_id: [49]
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS
            },
            "source_history_order": {
                method_id: "RECENT_FIRST"
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE60_METHODS
            },
            "source_native_protocol": SOURCE_NATIVE_WAVE60_PROTOCOL,
            "source_read_mode": "sqlite-mode=ro,immutable=1,query_only=ON",
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
    "LegacySeededBenchmarkNativeWave60BatchImportError",
    "materialize_legacy_seeded_benchmark_native_wave60_batch",
]
