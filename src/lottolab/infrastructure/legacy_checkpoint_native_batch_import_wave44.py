"""Causal materialization for the wave-44 frozen-checkpoint predictors."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from lottolab.application.biglotto_multi_ticket_backtest import (
    INPUT_SCHEMA_VERSION,
)
from lottolab.application.legacy_checkpoint_native_portfolios_wave44 import (
    CAUSAL_ELIGIBILITY_RULE,
    CHECKPOINT_BY_SOURCE_NATIVE_WAVE44_METHOD,
    CHECKPOINT_INTRODUCTION_COMMIT,
    CHECKPOINT_INTRODUCTION_LOCAL_DATE,
    CHECKPOINT_INTRODUCTION_TIME,
    DEFAULT_SOURCE_NATIVE_WAVE44_USER_SEED,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE44_METHOD,
    IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE44_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE44_METHOD,
    MODEL_CANDIDATE_K,
    MODEL_CONTEXT_DRAW_COUNT,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE44_METHOD,
    SOURCE_NATIVE_WAVE44_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE44_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS,
    LegacyCheckpointNativeWave44Request,
    generate_legacy_checkpoint_native_wave44_portfolio,
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

MATERIALIZATION_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_CHECKPOINT_NATIVE_WAVE44_BATCH_V1"
)
NONCAUSAL_TARGET_REASON = (
    "TARGET_NOT_STRICTLY_AFTER_CHECKPOINT_GIT_INTRODUCTION_LOCAL_DATE"
)


class LegacyCheckpointNativeWave44BatchImportError(ValueError):
    """The pinned dataset or checkpoint ledger violates the batch contract."""


def _catalog_records() -> dict[str, FullStrategyCatalogRecord]:
    catalog = load_full_strategy_catalog()
    by_method = {
        record.legacy_method_id: record for record in catalog.records
    }
    records: dict[str, FullStrategyCatalogRecord] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS:
        record = by_method.get(method_id)
        if (
            record is None
            or record.source_sha256
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE44_METHOD[method_id]
        ):
            raise LegacyCheckpointNativeWave44BatchImportError(
                "frozen checkpoint-native wave-44 catalog identity changed"
            )
        records[method_id] = record
    return records


def materialize_legacy_checkpoint_native_wave44_batch(
    *,
    database: Path,
    expected_database_sha256: str,
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE44_USER_SEED,
) -> dict[str, object]:
    """Build ordered-20 input while closing pre-checkpoint targets."""

    try:
        pinned_history = load_pinned_biglotto_history(
            database=database,
            expected_database_sha256=expected_database_sha256,
            require_replay_authority=False,
        )
    except ReplayBatchImportError as exc:
        raise LegacyCheckpointNativeWave44BatchImportError(str(exc)) from exc
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
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS:
        record = records[method_id]
        method_status_counts: Counter[str] = Counter()
        for target_index, target in enumerate(pinned_history.draws):
            if target.draw_date <= CHECKPOINT_INTRODUCTION_LOCAL_DATE:
                executions.append(
                    {
                        "reason_code": NONCAUSAL_TARGET_REASON,
                        "status": "CLOSED_REJECTED",
                        "strategy_id": record.strategy_id,
                        "strategy_version": record.strategy_version,
                        "target_draw_number": target.draw_number,
                    }
                )
                method_status_counts["CLOSED_REJECTED"] += 1
                aggregate_status_counts["CLOSED_REJECTED"] += 1
                continue
            prior_history = causal_history[:target_index]
            if len(prior_history) < MODEL_CONTEXT_DRAW_COUNT:
                raise LegacyCheckpointNativeWave44BatchImportError(
                    "causal target has insufficient frozen model context"
                )
            cutoff = pinned_history.draws[target_index - 1]
            native = generate_legacy_checkpoint_native_wave44_portfolio(
                LegacyCheckpointNativeWave44Request(
                    legacy_method_id=method_id,
                    target_draw_number=target.draw_number,
                    target_draw_date=target.draw_date,
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
                raise LegacyCheckpointNativeWave44BatchImportError(
                    "ordered-20 construction failed: "
                    f"{constructed.reason.value}"
                )
            executions.append(
                {
                    "candidate_k": MODEL_CANDIDATE_K,
                    "combination_count": native.metadata.combination_count,
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
            f"legacy-biglotto-checkpoint-native-wave44-"
            f"{pinned_history.database_sha256_before[:12]}"
        ),
        "dataset_sha256": pinned_history.database_sha256_before,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "candidate_k": {
                method_id: MODEL_CANDIDATE_K
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS
            },
            "candidate_k_semantics": (
                "FULL_49_LEGAL_NUMBER_MODEL_RANKING_DISTINCT_FROM_ONE_"
                "NATIVE_TICKET_NO_METHOD_COMBINATION_AND_ORDERED20_COUNT"
            ),
            "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
            "checkpoint_artifacts": dict(
                CHECKPOINT_BY_SOURCE_NATIVE_WAVE44_METHOD
            ),
            "checkpoint_introduction_commit": (
                CHECKPOINT_INTRODUCTION_COMMIT
            ),
            "checkpoint_introduction_time": (
                CHECKPOINT_INTRODUCTION_TIME
            ),
            "combination_count": {
                method_id: None
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS
            },
            "combination_count_semantics": (
                "NULL_SINGLE_LOCAL_SOURCE_CONFIGURATION_IMPORTED_"
                "COMPARATORS_EXCLUDED"
            ),
            "constructor": CONSTRUCTOR_IDENTIFIER,
            "database_sha256_after": pinned_history.database_sha256_after,
            "database_sha256_before": (
                pinned_history.database_sha256_before
            ),
            "execution_status_counts": dict(
                sorted(aggregate_status_counts.items())
            ),
            "execution_status_counts_by_method": status_counts_by_method,
            "frozen_sources": dict(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE44_METHOD
            ),
            "frozen_support_artifacts": dict(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE44_METHOD
            ),
            "imported_comparators_excluded": dict(
                IMPORTED_COMPARATORS_EXCLUDED_BY_SOURCE_NATIVE_WAVE44_METHOD
            ),
            "ledger_content_sha256": LEDGER_CONTENT_SHA256,
            "ledger_file_sha256": LEDGER_FILE_SHA256,
            "ledger_schema_version": LEDGER_SCHEMA_VERSION,
            "local_source_configurations": dict(
                LOCAL_SOURCE_CONFIGURATION_BY_SOURCE_NATIVE_WAVE44_METHOD
            ),
            "model_context_draw_count": MODEL_CONTEXT_DRAW_COUNT,
            "native_ticket_count": {
                method_id: 1
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS
            },
            "native_ticket_semantics": dict(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE44_METHOD
            ),
            "random_protocols": {
                method_id: (
                    "NONE_FROZEN_CHECKPOINT_MODEL_EVAL_TOP_LOGIT_SELECTION"
                )
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS
            },
            "replay_truth_supplemented_draw_count": (
                pinned_history.replay_truth_supplemented_draw_count
            ),
            "source_history_order": {
                method_id: "OLDEST_FIRST"
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE44_METHODS
            },
            "source_native_protocol": SOURCE_NATIVE_WAVE44_PROTOCOL,
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
    "NONCAUSAL_TARGET_REASON",
    "LegacyCheckpointNativeWave44BatchImportError",
    "materialize_legacy_checkpoint_native_wave44_batch",
]
