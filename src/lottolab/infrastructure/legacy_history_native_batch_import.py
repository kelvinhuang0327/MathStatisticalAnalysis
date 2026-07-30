"""Causal materialization for four frozen history-native BIG_LOTTO methods."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from lottolab.application.biglotto_multi_ticket_backtest import INPUT_SCHEMA_VERSION
from lottolab.application.legacy_history_native_portfolios import (
    DEFAULT_HISTORY_NATIVE_USER_SEED,
    HISTORY_NATIVE_PROTOCOL,
    MINIMUM_HISTORY_BY_HISTORY_NATIVE_METHOD,
    NATIVE_TICKET_COUNT_BY_HISTORY_NATIVE_METHOD,
    QUICK_ML_PATTERN_SLICE_REASON,
    RANDOM_PROTOCOL_BY_HISTORY_NATIVE_METHOD,
    SOURCE_SHA256_BY_HISTORY_NATIVE_METHOD,
    SUPPORTED_HISTORY_NATIVE_METHODS,
    LegacyHistoryDraw,
    LegacyHistoryNativeRequest,
    LegacyHistoryNativeSourceError,
    generate_legacy_history_native_portfolio,
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

MATERIALIZATION_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_HISTORY_NATIVE_BATCH_V1"


class LegacyHistoryNativeBatchImportError(ValueError):
    """The source DB or frozen strategy cannot satisfy this batch contract."""


def _catalog_records() -> tuple[FullStrategyCatalogRecord, ...]:
    catalog = load_full_strategy_catalog()
    by_method_id = {
        record.legacy_method_id: record for record in catalog.records
    }
    records: list[FullStrategyCatalogRecord] = []
    for method_id in SUPPORTED_HISTORY_NATIVE_METHODS:
        record = by_method_id.get(method_id)
        if (
            record is None
            or record.source_sha256
            != SOURCE_SHA256_BY_HISTORY_NATIVE_METHOD[method_id]
        ):
            raise LegacyHistoryNativeBatchImportError(
                "frozen history-native catalog identity changed"
            )
        records.append(record)
    return tuple(records)


def materialize_legacy_history_native_batch(
    *,
    database: Path,
    expected_database_sha256: str,
    user_seed: str | int = DEFAULT_HISTORY_NATIVE_USER_SEED,
) -> dict[str, object]:
    """Build one ordered-20 evaluator input for four history-native methods."""

    try:
        pinned_history = load_pinned_biglotto_history(
            database=database,
            expected_database_sha256=expected_database_sha256,
        )
    except ReplayBatchImportError as exc:
        raise LegacyHistoryNativeBatchImportError(str(exc)) from exc
    records = _catalog_records()
    causal_history = tuple(
        LegacyHistoryDraw(draw_number=draw.draw_number, numbers=draw.numbers)
        for draw in pinned_history.draws
    )
    executions: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    status_counts_by_method: dict[str, Counter[str]] = defaultdict(Counter)

    for target_index, target in enumerate(pinned_history.draws):
        prior_history = causal_history[:target_index]
        for record in records:
            minimum_history = MINIMUM_HISTORY_BY_HISTORY_NATIVE_METHOD[
                record.legacy_method_id
            ]
            if len(prior_history) < minimum_history:
                row: dict[str, object] = {
                    "reason_code": (
                        "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
                    ),
                    "status": "CLOSED_INSUFFICIENT_HISTORY",
                    "strategy_id": record.strategy_id,
                    "strategy_version": record.strategy_version,
                    "target_draw_number": target.draw_number,
                }
                executions.append(row)
                status_counts["CLOSED_INSUFFICIENT_HISTORY"] += 1
                status_counts_by_method[record.legacy_method_id][
                    "CLOSED_INSUFFICIENT_HISTORY"
                ] += 1
                continue

            cutoff = pinned_history.draws[target_index - 1]
            try:
                native = generate_legacy_history_native_portfolio(
                    LegacyHistoryNativeRequest(
                        legacy_method_id=record.legacy_method_id,
                        target_draw_number=target.draw_number,
                        history=prior_history,
                        replicate_id=0,
                        user_seed=user_seed,
                    )
                )
            except LegacyHistoryNativeSourceError as exc:
                if (
                    record.legacy_method_id
                    != "tools/quick_ml_predict.py"
                    or exc.reason_code != QUICK_ML_PATTERN_SLICE_REASON
                ):
                    raise LegacyHistoryNativeBatchImportError(
                        f"unexpected frozen-source failure: {exc.reason_code}"
                    ) from exc
                row = {
                    "history_cutoff_draw_date": cutoff.draw_date.isoformat(),
                    "history_cutoff_draw_number": cutoff.draw_number,
                    "reason_code": exc.reason_code,
                    "status": "CLOSED_EXECUTION_ERROR",
                    "strategy_id": record.strategy_id,
                    "strategy_version": record.strategy_version,
                    "target_draw_number": target.draw_number,
                }
                executions.append(row)
                status_counts["CLOSED_EXECUTION_ERROR"] += 1
                status_counts_by_method[record.legacy_method_id][
                    "CLOSED_EXECUTION_ERROR"
                ] += 1
                continue

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
                raise LegacyHistoryNativeBatchImportError(
                    f"ordered-20 construction failed: {constructed.reason.value}"
                )
            executions.append(
                {
                    "history_cutoff_draw_date": cutoff.draw_date.isoformat(),
                    "history_cutoff_draw_number": cutoff.draw_number,
                    "native_generation": native.metadata.canonical_dict(),
                    "native_ticket_count": len(native.tickets),
                    "native_tickets": [list(ticket) for ticket in native.tickets],
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
            status_counts["OK"] += 1
            status_counts_by_method[record.legacy_method_id]["OK"] += 1

    targets = [
        {
            "draw_date": draw.draw_date.isoformat(),
            "draw_number": draw.draw_number,
            "winning_main_numbers": list(draw.numbers),
            "winning_special_number": draw.special,
        }
        for draw in pinned_history.draws
    ]
    return {
        "dataset_id": (
            f"legacy-biglotto-history-native4-"
            f"{pinned_history.database_sha256_before[:12]}"
        ),
        "dataset_sha256": pinned_history.database_sha256_before,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "constructor": CONSTRUCTOR_IDENTIFIER,
            "database_sha256_after": pinned_history.database_sha256_after,
            "database_sha256_before": pinned_history.database_sha256_before,
            "execution_status_counts": dict(sorted(status_counts.items())),
            "execution_status_counts_by_method": {
                method_id: dict(sorted(status_counts_by_method[method_id].items()))
                for method_id in SUPPORTED_HISTORY_NATIVE_METHODS
            },
            "frozen_sources": dict(SOURCE_SHA256_BY_HISTORY_NATIVE_METHOD),
            "history_native_protocol": HISTORY_NATIVE_PROTOCOL,
            "minimum_history_draws": dict(
                MINIMUM_HISTORY_BY_HISTORY_NATIVE_METHOD
            ),
            "native_ticket_count_per_success": dict(
                NATIVE_TICKET_COUNT_BY_HISTORY_NATIVE_METHOD
            ),
            "random_protocols": dict(
                RANDOM_PROTOCOL_BY_HISTORY_NATIVE_METHOD
            ),
            "replay_truth_supplemented_draw_count": (
                pinned_history.replay_truth_supplemented_draw_count
            ),
            "source_read_mode": "sqlite-mode=ro,immutable=1,query_only=ON",
            "user_seed": user_seed,
        },
        "targets": targets,
    }


__all__ = [
    "MATERIALIZATION_SCHEMA_VERSION",
    "LegacyHistoryNativeBatchImportError",
    "materialize_legacy_history_native_batch",
]
