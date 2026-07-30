"""Causal materialization for the fifth frozen history-native BIG_LOTTO batch."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from lottolab.application.biglotto_multi_ticket_backtest import INPUT_SCHEMA_VERSION
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_history_native_portfolios_wave5 import (
    DEFAULT_HISTORY_NATIVE_WAVE5_USER_SEED,
    HISTORY_NATIVE_WAVE5_PROTOCOL,
    MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE5_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE5_METHOD,
    RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE5_METHOD,
    SOURCE_CANDIDATE_TICKET_COUNTS_BY_HISTORY_NATIVE_WAVE5_METHOD,
    SOURCE_COMBINATION_COUNT_BY_HISTORY_NATIVE_WAVE5_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_HISTORY_NATIVE_WAVE5_METHOD,
    SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE5_METHOD,
    SUPPORTED_HISTORY_NATIVE_WAVE5_METHODS,
    LegacyHistoryNativeWave5Request,
    LegacyHistoryNativeWave5SourceError,
    generate_legacy_history_native_wave5_portfolio,
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
    "BIG_LOTTO_LEGACY_HISTORY_NATIVE_WAVE5_BATCH_V1"
)


class LegacyHistoryNativeWave5BatchImportError(ValueError):
    """The source DB or frozen strategy cannot satisfy this batch contract."""


def _catalog_records() -> tuple[FullStrategyCatalogRecord, ...]:
    catalog = load_full_strategy_catalog()
    by_method_id = {
        record.legacy_method_id: record for record in catalog.records
    }
    records: list[FullStrategyCatalogRecord] = []
    for method_id in SUPPORTED_HISTORY_NATIVE_WAVE5_METHODS:
        record = by_method_id.get(method_id)
        if (
            record is None
            or record.source_sha256
            != SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE5_METHOD[method_id]
        ):
            raise LegacyHistoryNativeWave5BatchImportError(
                "frozen history-native wave-5 catalog identity changed"
            )
        records.append(record)
    return tuple(records)


def materialize_legacy_history_native_wave5_batch(
    *,
    database: Path,
    expected_database_sha256: str,
    user_seed: str | int = DEFAULT_HISTORY_NATIVE_WAVE5_USER_SEED,
) -> dict[str, object]:
    """Build ordered-20 evaluator input for three more history-native methods."""

    try:
        pinned_history = load_pinned_biglotto_history(
            database=database,
            expected_database_sha256=expected_database_sha256,
        )
    except ReplayBatchImportError as exc:
        raise LegacyHistoryNativeWave5BatchImportError(str(exc)) from exc
    records = _catalog_records()
    causal_history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in pinned_history.draws
    )
    executions: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    status_counts_by_method: dict[str, Counter[str]] = defaultdict(
        Counter
    )

    for target_index, target in enumerate(pinned_history.draws):
        prior_history = causal_history[:target_index]
        for record in records:
            method_id = record.legacy_method_id
            minimum_history = (
                MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE5_METHOD[method_id]
            )
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
                status_counts_by_method[method_id][
                    "CLOSED_INSUFFICIENT_HISTORY"
                ] += 1
                continue

            cutoff = pinned_history.draws[target_index - 1]
            try:
                native = generate_legacy_history_native_wave5_portfolio(
                    LegacyHistoryNativeWave5Request(
                        legacy_method_id=method_id,
                        target_draw_number=target.draw_number,
                        history=prior_history,
                        replicate_id=0,
                        user_seed=user_seed,
                    )
                )
            except LegacyHistoryNativeWave5SourceError as exc:
                raise LegacyHistoryNativeWave5BatchImportError(
                    f"unexpected frozen-source failure: {exc.reason_code}"
                ) from exc

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
                raise LegacyHistoryNativeWave5BatchImportError(
                    "ordered-20 construction failed: "
                    f"{constructed.reason.value}"
                )
            execution: dict[str, object] = {
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
            combination_count = (
                SOURCE_COMBINATION_COUNT_BY_HISTORY_NATIVE_WAVE5_METHOD[
                    method_id
                ]
            )
            if combination_count is not None:
                execution["combination_count"] = combination_count
            executions.append(execution)
            status_counts["OK"] += 1
            status_counts_by_method[method_id]["OK"] += 1

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
            f"legacy-biglotto-history-native-wave5-"
            f"{pinned_history.database_sha256_before[:12]}"
        ),
        "dataset_sha256": pinned_history.database_sha256_before,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "candidate_k": {
                method_id: None
                for method_id in SUPPORTED_HISTORY_NATIVE_WAVE5_METHODS
            },
            "combination_count": dict(
                SOURCE_COMBINATION_COUNT_BY_HISTORY_NATIVE_WAVE5_METHOD
            ),
            "combination_members": dict(
                SOURCE_COMBINATION_MEMBERS_BY_HISTORY_NATIVE_WAVE5_METHOD
            ),
            "constructor": CONSTRUCTOR_IDENTIFIER,
            "database_sha256_after": (
                pinned_history.database_sha256_after
            ),
            "database_sha256_before": (
                pinned_history.database_sha256_before
            ),
            "execution_status_counts": dict(
                sorted(status_counts.items())
            ),
            "execution_status_counts_by_method": {
                method_id: dict(
                    sorted(status_counts_by_method[method_id].items())
                )
                for method_id in SUPPORTED_HISTORY_NATIVE_WAVE5_METHODS
            },
            "frozen_sources": dict(
                SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE5_METHOD
            ),
            "history_native_protocol": HISTORY_NATIVE_WAVE5_PROTOCOL,
            "minimum_history_draws": dict(
                MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE5_METHOD
            ),
            "native_ticket_semantics": dict(
                NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE5_METHOD
            ),
            "random_protocols": dict(
                RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE5_METHOD
            ),
            "replay_truth_supplemented_draw_count": (
                pinned_history.replay_truth_supplemented_draw_count
            ),
            "source_candidate_ticket_counts": dict(
                SOURCE_CANDIDATE_TICKET_COUNTS_BY_HISTORY_NATIVE_WAVE5_METHOD
            ),
            "source_history_order": {
                method_id: "OLDEST_FIRST"
                for method_id in SUPPORTED_HISTORY_NATIVE_WAVE5_METHODS
            },
            "source_read_mode": (
                "sqlite-mode=ro,immutable=1,query_only=ON"
            ),
            "user_seed": user_seed,
        },
        "targets": targets,
    }


__all__ = [
    "MATERIALIZATION_SCHEMA_VERSION",
    "LegacyHistoryNativeWave5BatchImportError",
    "materialize_legacy_history_native_wave5_batch",
]
