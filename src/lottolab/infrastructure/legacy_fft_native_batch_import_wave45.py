"""Causal materialization for the wave-45 frozen FFT source batch."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from lottolab.application.biglotto_multi_ticket_backtest import (
    INPUT_SCHEMA_VERSION,
)
from lottolab.application.legacy_fft_native_portfolios_wave45 import (
    CONTEXT_DRAW_COUNT,
    DEFAULT_SOURCE_NATIVE_WAVE45_USER_SEED,
    FROZEN_SOURCE_COMMIT,
    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE45_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE45_METHOD,
    MODEL_CANDIDATE_K,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE45_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE45_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE45_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE45_METHOD,
    SOURCE_NATIVE_WAVE45_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE45_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS,
    TRIPLE_ALIAS_METHOD_ID,
    TRIPLE_ORIGINAL_METHOD_ID,
    LegacyFftNativeWave45Request,
    generate_legacy_fft_native_wave45_portfolio,
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
    ReplayBatchImportError,
    load_pinned_biglotto_history,
)

MATERIALIZATION_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_FFT_NATIVE_WAVE45_BATCH_V1"
CLOSED_REASON = "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"


class LegacyFftNativeWave45BatchImportError(ValueError):
    """The pinned dataset or source ledger violates the batch contract."""


def _catalog_records() -> dict[str, FullStrategyCatalogRecord]:
    catalog = load_full_strategy_catalog()
    by_method = {record.legacy_method_id: record for record in catalog.records}
    records: dict[str, FullStrategyCatalogRecord] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS:
        record = by_method.get(method_id)
        if (
            record is None
            or record.source_sha256 != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id]
        ):
            raise LegacyFftNativeWave45BatchImportError(
                "frozen FFT wave-45 catalog identity changed"
            )
        records[method_id] = record
    return records


def materialize_legacy_fft_native_wave45_batch(
    *,
    database: Path,
    expected_database_sha256: str,
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE45_USER_SEED,
) -> dict[str, object]:
    """Build ordered-20 evaluator input for four executable source rows."""

    try:
        pinned_history = load_pinned_biglotto_history(
            database=database,
            expected_database_sha256=expected_database_sha256,
            require_replay_authority=False,
        )
    except ReplayBatchImportError as exc:
        raise LegacyFftNativeWave45BatchImportError(str(exc)) from exc
    records = _catalog_records()
    causal_history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in pinned_history.draws
    )
    executions: list[dict[str, object]] = []
    aggregate_status_counts: Counter[str] = Counter()
    status_counts_by_method: dict[str, dict[str, int]] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS:
        record = records[method_id]
        minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id]
        method_status_counts: Counter[str] = Counter()
        for target_index, target in enumerate(pinned_history.draws):
            prior_history = causal_history[:target_index]
            if len(prior_history) < minimum:
                executions.append(
                    {
                        "reason_code": CLOSED_REASON,
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
            native = generate_legacy_fft_native_wave45_portfolio(
                LegacyFftNativeWave45Request(
                    legacy_method_id=method_id,
                    target_draw_number=target.draw_number,
                    history=prior_history,
                    dataset_sha256=pinned_history.database_sha256_before,
                    replicate_id=0,
                    user_seed=user_seed,
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
                raise LegacyFftNativeWave45BatchImportError(
                    f"ordered-20 construction failed: {constructed.reason.value}"
                )
            executions.append(
                {
                    "candidate_k": MODEL_CANDIDATE_K,
                    "combination_count": (
                        SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id]
                    ),
                    "history_cutoff_draw_date": (cutoff.draw_date.isoformat()),
                    "history_cutoff_draw_number": cutoff.draw_number,
                    "native_generation": native.metadata.canonical_dict(),
                    "native_ticket_count": len(native.tickets),
                    "native_tickets": [list(ticket) for ticket in native.tickets],
                    "ordered_portfolio": [list(ticket) for ticket in constructed.tickets],
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
        status_counts_by_method[method_id] = dict(sorted(method_status_counts.items()))
    return {
        "dataset_id": (
            f"legacy-biglotto-fft-native-wave45-{pinned_history.database_sha256_before[:12]}"
        ),
        "dataset_sha256": pinned_history.database_sha256_before,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "alias_disposition": {
                "alias_method": TRIPLE_ALIAS_METHOD_ID,
                "canonical_method": TRIPLE_ORIGINAL_METHOD_ID,
                "overlapping_causal_output_case_count": 1648,
            },
            "candidate_k": {
                method_id: MODEL_CANDIDATE_K for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS
            },
            "candidate_k_semantics": (
                "FULL_49_LEGAL_NUMBER_RANKING_OR_SELECTION_DOMAIN_"
                "DISTINCT_FROM_NATIVE_TICKET_COUNT_SOURCE_CONFIGURATION_"
                "COUNT_AND_ORDERED20_COUNT"
            ),
            "combination_count": {
                method_id: (SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id])
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS
            },
            "combination_count_semantics": (
                "NULL_FOR_SINGLE_SOURCE_CONFIGURATION_OR_TWO_FOR_PAIRED_"
                "LOCAL_CONFIGURATIONS_DISTINCT_FROM_CANDIDATE_K_NATIVE_"
                "TICKET_COUNT_AND_ORDERED20_COUNT"
            ),
            "combination_members": {
                method_id: list(
                    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id]
                )
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS
            },
            "constructor": CONSTRUCTOR_IDENTIFIER,
            "context_draw_count": CONTEXT_DRAW_COUNT,
            "database_sha256_after": pinned_history.database_sha256_after,
            "database_sha256_before": (pinned_history.database_sha256_before),
            "execution_status_counts": dict(sorted(aggregate_status_counts.items())),
            "execution_status_counts_by_method": status_counts_by_method,
            "frozen_source_commit": FROZEN_SOURCE_COMMIT,
            "frozen_sources": {
                method_id: (SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id])
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS
            },
            "intra_ticket_order_semantics": {
                method_id: (INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id])
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS
            },
            "ledger_content_sha256": LEDGER_CONTENT_SHA256,
            "ledger_file_sha256": LEDGER_FILE_SHA256,
            "ledger_schema_version": LEDGER_SCHEMA_VERSION,
            "minimum_history_draws": {
                method_id: (MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id])
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS
            },
            "native_ticket_count": {
                method_id: (NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id])
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS
            },
            "native_ticket_semantics": {
                method_id: (NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE45_METHOD[method_id])
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS
            },
            "random_protocols": {
                method_id: "NONE_DETERMINISTIC_FROZEN_SOURCE"
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS
            },
            "replay_truth_supplemented_draw_count": (
                pinned_history.replay_truth_supplemented_draw_count
            ),
            "source_history_order": {
                method_id: "OLDEST_FIRST" for method_id in SUPPORTED_SOURCE_NATIVE_WAVE45_METHODS
            },
            "source_native_protocol": SOURCE_NATIVE_WAVE45_PROTOCOL,
            "source_read_mode": ("sqlite-mode=ro,immutable=1,query_only=ON"),
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
    "CLOSED_REASON",
    "MATERIALIZATION_SCHEMA_VERSION",
    "LegacyFftNativeWave45BatchImportError",
    "materialize_legacy_fft_native_wave45_batch",
]
