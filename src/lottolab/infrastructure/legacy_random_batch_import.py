"""Causal materialization for frozen Core-Satellite and Zone Split methods."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from lottolab.application.biglotto_multi_ticket_backtest import INPUT_SCHEMA_VERSION
from lottolab.application.legacy_random_native_portfolios import (
    CORE_SATELLITE_METHOD_ID,
    CORE_SATELLITE_SOURCE_SHA256,
    DEFAULT_USER_SEED,
    RANDOM_NATIVE_PROTOCOL,
    SUPPORTED_RANDOM_NATIVE_METHODS,
    ZONE_SPLIT_METHOD_ID,
    ZONE_SPLIT_SOURCE_SHA256,
    LegacyRandomNativeRequest,
    generate_legacy_random_native_portfolio,
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

MATERIALIZATION_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_RANDOM_NATIVE_BATCH_V1"
_SOURCE_SHA256_BY_METHOD = {
    CORE_SATELLITE_METHOD_ID: CORE_SATELLITE_SOURCE_SHA256,
    ZONE_SPLIT_METHOD_ID: ZONE_SPLIT_SOURCE_SHA256,
}


class LegacyRandomBatchImportError(ValueError):
    """The source DB or frozen strategy cannot satisfy this batch contract."""


def _catalog_records() -> tuple[FullStrategyCatalogRecord, ...]:
    catalog = load_full_strategy_catalog()
    by_method_id = {
        record.legacy_method_id: record for record in catalog.records
    }
    records: list[FullStrategyCatalogRecord] = []
    for method_id in SUPPORTED_RANDOM_NATIVE_METHODS:
        record = by_method_id.get(method_id)
        if (
            record is None
            or record.source_sha256 != _SOURCE_SHA256_BY_METHOD[method_id]
        ):
            raise LegacyRandomBatchImportError(
                "frozen random-native catalog identity changed"
            )
        records.append(record)
    return tuple(records)


def materialize_legacy_random_native_batch(
    *,
    database: Path,
    expected_database_sha256: str,
    user_seed: str | int = DEFAULT_USER_SEED,
) -> dict[str, object]:
    """Build one ordered-20 evaluator input for both random-native methods."""

    try:
        history = load_pinned_biglotto_history(
            database=database,
            expected_database_sha256=expected_database_sha256,
        )
    except ReplayBatchImportError as exc:
        raise LegacyRandomBatchImportError(str(exc)) from exc
    records = _catalog_records()
    executions: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    for target_index, target in enumerate(history.draws):
        for record in records:
            if target_index == 0:
                executions.append(
                    {
                        "reason_code": "NO_PRIOR_DRAW_FOR_CAUSAL_CUTOFF",
                        "status": "CLOSED_INSUFFICIENT_HISTORY",
                        "strategy_id": record.strategy_id,
                        "strategy_version": record.strategy_version,
                        "target_draw_number": target.draw_number,
                    }
                )
                status_counts["CLOSED_INSUFFICIENT_HISTORY"] += 1
                continue
            cutoff = history.draws[target_index - 1]
            native = generate_legacy_random_native_portfolio(
                LegacyRandomNativeRequest(
                    legacy_method_id=record.legacy_method_id,
                    target_draw_number=target.draw_number,
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
                raise LegacyRandomBatchImportError(
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

    targets = [
        {
            "draw_date": draw.draw_date.isoformat(),
            "draw_number": draw.draw_number,
            "winning_main_numbers": list(draw.numbers),
            "winning_special_number": draw.special,
        }
        for draw in history.draws
    ]
    return {
        "dataset_id": (
            f"legacy-biglotto-random-native2-"
            f"{history.database_sha256_before[:12]}"
        ),
        "dataset_sha256": history.database_sha256_before,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "constructor": CONSTRUCTOR_IDENTIFIER,
            "database_sha256_after": history.database_sha256_after,
            "database_sha256_before": history.database_sha256_before,
            "execution_status_counts": dict(sorted(status_counts.items())),
            "frozen_sources": {
                method_id: _SOURCE_SHA256_BY_METHOD[method_id]
                for method_id in SUPPORTED_RANDOM_NATIVE_METHODS
            },
            "native_ticket_count_per_success": 3,
            "random_native_protocol": RANDOM_NATIVE_PROTOCOL,
            "replay_truth_supplemented_draw_count": (
                history.replay_truth_supplemented_draw_count
            ),
            "source_read_mode": "sqlite-mode=ro,immutable=1,query_only=ON",
            "user_seed": user_seed,
        },
        "targets": targets,
    }


__all__ = [
    "MATERIALIZATION_SCHEMA_VERSION",
    "LegacyRandomBatchImportError",
    "materialize_legacy_random_native_batch",
]
