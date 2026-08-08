"""Causal materialization for the thirty-second frozen source-native batch."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from lottolab.application.biglotto_multi_ticket_backtest import INPUT_SCHEMA_VERSION
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave32 import (
    DEFAULT_SOURCE_NATIVE_WAVE32_USER_SEED,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE32_METHOD,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE32_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE32_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE32_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE32_METHOD,
    SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE32_METHOD,
    SOURCE_NATIVE_WAVE32_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE32_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE32_METHODS,
    LegacySourceNativeWave32Request,
    generate_legacy_source_native_wave32_portfolio,
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
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE32_BATCH_V1"
)


class LegacySourceNativeWave32BatchImportError(ValueError):
    """The source DB or frozen strategy cannot satisfy this batch contract."""


def _catalog_record() -> FullStrategyCatalogRecord:
    catalog = load_full_strategy_catalog()
    by_method_id = {
        record.legacy_method_id: record for record in catalog.records
    }
    method_id = SUPPORTED_SOURCE_NATIVE_WAVE32_METHODS[0]
    record = by_method_id.get(method_id)
    if (
        record is None
        or record.source_sha256
        != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE32_METHOD[method_id]
    ):
        raise LegacySourceNativeWave32BatchImportError(
            "frozen source-native wave-32 catalog identity changed"
        )
    return record


def materialize_legacy_source_native_wave32_batch(
    *,
    database: Path,
    expected_database_sha256: str,
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE32_USER_SEED,
) -> dict[str, object]:
    """Build ordered-20 evaluator input for the eleven-variant method."""

    try:
        pinned_history = load_pinned_biglotto_history(
            database=database,
            expected_database_sha256=expected_database_sha256,
            require_replay_authority=False,
        )
    except ReplayBatchImportError as exc:
        raise LegacySourceNativeWave32BatchImportError(str(exc)) from exc
    record = _catalog_record()
    method_id = record.legacy_method_id
    causal_history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in pinned_history.draws
    )
    executions: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE32_METHOD[method_id]
    for target_index, target in enumerate(pinned_history.draws):
        prior_history = causal_history[:target_index]
        if len(prior_history) < minimum:
            executions.append(
                {
                    "reason_code": (
                        "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
                    ),
                    "status": "CLOSED_INSUFFICIENT_HISTORY",
                    "strategy_id": record.strategy_id,
                    "strategy_version": record.strategy_version,
                    "target_draw_number": target.draw_number,
                }
            )
            status_counts["CLOSED_INSUFFICIENT_HISTORY"] += 1
            continue
        cutoff = pinned_history.draws[target_index - 1]
        native = generate_legacy_source_native_wave32_portfolio(
            LegacySourceNativeWave32Request(
                legacy_method_id=method_id,
                target_draw_number=target.draw_number,
                history=prior_history,
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
            raise LegacySourceNativeWave32BatchImportError(
                "ordered-20 construction failed: "
                f"{constructed.reason.value}"
            )
        executions.append(
            {
                "candidate_k": native.metadata.candidate_k,
                "combination_count": (
                    native.metadata.source_method_combination_count
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
                "portfolio_derivation": CONSTRUCTOR_IDENTIFIER,
                "portfolio_ticket_count": 20,
                "status": "OK",
                "strategy_id": record.strategy_id,
                "strategy_version": record.strategy_version,
                "target_draw_number": target.draw_number,
            }
        )
        status_counts["OK"] += 1
    return {
        "dataset_id": (
            f"legacy-biglotto-source-native-wave32-"
            f"{pinned_history.database_sha256_before[:12]}"
        ),
        "dataset_sha256": pinned_history.database_sha256_before,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "candidate_k_semantics": (
                "NULL_NO_COMBINATORIAL_CANDIDATE_K_DISTINCT_FROM_"
                "ELEVEN_VARIANT_CONFIGURATIONS_NATIVE_TICKETS_AND_"
                "ORDERED20_COUNT"
            ),
            "combination_count": dict(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD
            ),
            "combination_count_semantics": (
                "SOURCE_VARIANT_CONFIGURATION_COUNT_DISTINCT_FROM_"
                "CANDIDATE_K_NATIVE_TICKETS_AND_ORDERED20_COUNT"
            ),
            "combination_members": dict(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE32_METHOD
            ),
            "constructor": CONSTRUCTOR_IDENTIFIER,
            "database_sha256_after": (
                pinned_history.database_sha256_after
            ),
            "database_sha256_before": (
                pinned_history.database_sha256_before
            ),
            "execution_status_counts": dict(sorted(status_counts.items())),
            "execution_status_counts_by_method": {
                method_id: dict(sorted(status_counts.items()))
            },
            "frozen_sources": dict(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE32_METHOD
            ),
            "frozen_support_artifacts": dict(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE32_METHOD
            ),
            "minimum_history_draws": dict(
                MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE32_METHOD
            ),
            "native_ticket_count": dict(
                NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE32_METHOD
            ),
            "native_ticket_semantics": dict(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE32_METHOD
            ),
            "random_protocols": {
                method_id: (
                    "PYTHON_RANDOM_MODULE_SEEDED_WITH_VARIANT_HISTORY_"
                    "LENGTH_FOR_STATISTICAL_POSITIONS_4_5_6"
                )
            },
            "replay_truth_supplemented_draw_count": (
                pinned_history.replay_truth_supplemented_draw_count
            ),
            "source_history_order": dict(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE32_METHOD
            ),
            "source_history_order_detail": dict(
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE32_METHOD
            ),
            "source_native_protocol": SOURCE_NATIVE_WAVE32_PROTOCOL,
            "source_read_mode": "sqlite-mode=ro,immutable=1,query_only=ON",
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
    "LegacySourceNativeWave32BatchImportError",
    "materialize_legacy_source_native_wave32_batch",
]
