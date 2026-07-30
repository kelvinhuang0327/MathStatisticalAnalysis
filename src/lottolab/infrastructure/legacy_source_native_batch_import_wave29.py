"""Causal materialization for the twenty-ninth frozen source-native batch."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from lottolab.application.biglotto_multi_ticket_backtest import INPUT_SCHEMA_VERSION
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave29 import (
    DEFAULT_SOURCE_NATIVE_WAVE29_USER_SEED,
    FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE29_METHOD,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE29_METHOD,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE29_METHOD,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SOURCE_NATIVE_WAVE29_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD,
    SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS,
    LegacySourceNativeWave29Request,
    LegacySourceNativeWave29SourceError,
    frozen_wave29_engine_output,
    generate_legacy_source_native_wave29_portfolio,
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
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE29_BATCH_V1"
)
_ENGINE_CONFIGURATIONS = (
    ("markov", 50),
    ("markov", 100),
    ("deviation", 100),
    ("deviation", 200),
    ("statistical", 100),
    ("statistical", 110),
)


class LegacySourceNativeWave29BatchImportError(ValueError):
    """The source DB or frozen strategy cannot satisfy this batch contract."""


def _catalog_records() -> tuple[FullStrategyCatalogRecord, ...]:
    catalog = load_full_strategy_catalog()
    by_method_id = {
        record.legacy_method_id: record for record in catalog.records
    }
    records: list[FullStrategyCatalogRecord] = []
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS:
        record = by_method_id.get(method_id)
        if (
            record is None
            or record.source_sha256
            != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD[method_id]
        ):
            raise LegacySourceNativeWave29BatchImportError(
                "frozen source-native wave-29 catalog identity changed"
            )
        records.append(record)
    return tuple(records)


def _closed_row(
    *,
    record: FullStrategyCatalogRecord,
    target_draw_number: str,
    status: str,
    reason_code: str,
) -> dict[str, object]:
    return {
        "reason_code": reason_code,
        "status": status,
        "strategy_id": record.strategy_id,
        "strategy_version": record.strategy_version,
        "target_draw_number": target_draw_number,
    }


def _target_engine_cache(
    history: tuple[LegacyHistoryDraw, ...],
) -> dict[tuple[int, str], tuple[int, ...]]:
    cache: dict[tuple[int, str], tuple[int, ...]] = {}
    for method_name, window in _ENGINE_CONFIGURATIONS:
        analysis_history = history[-window:]
        key = (len(analysis_history), method_name)
        if key in cache:
            continue
        try:
            cache[key] = frozen_wave29_engine_output(
                method_name,
                analysis_history,
            )
        except Exception:
            continue
    return cache


def materialize_legacy_source_native_wave29_batch(
    *,
    database: Path,
    expected_database_sha256: str,
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE29_USER_SEED,
) -> dict[str, object]:
    """Build ordered-20 evaluator input for two rolling Elite-7 methods."""

    try:
        pinned_history = load_pinned_biglotto_history(
            database=database,
            expected_database_sha256=expected_database_sha256,
        )
    except ReplayBatchImportError as exc:
        raise LegacySourceNativeWave29BatchImportError(str(exc)) from exc
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
        engine_cache = (
            _target_engine_cache(prior_history) if prior_history else {}
        )
        for record in records:
            method_id = record.legacy_method_id
            minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE29_METHOD[
                method_id
            ]
            if len(prior_history) < minimum:
                status = "CLOSED_INSUFFICIENT_HISTORY"
                executions.append(
                    _closed_row(
                        record=record,
                        target_draw_number=target.draw_number,
                        status=status,
                        reason_code=(
                            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
                        ),
                    )
                )
                status_counts[status] += 1
                status_counts_by_method[method_id][status] += 1
                continue
            cutoff = pinned_history.draws[target_index - 1]
            try:
                native = generate_legacy_source_native_wave29_portfolio(
                    LegacySourceNativeWave29Request(
                        legacy_method_id=method_id,
                        target_draw_number=target.draw_number,
                        history=prior_history,
                        replicate_id=0,
                        user_seed=user_seed,
                    ),
                    engine_cache=engine_cache,
                )
            except LegacySourceNativeWave29SourceError as exc:
                status = "CLOSED_EXECUTION_ERROR"
                executions.append(
                    _closed_row(
                        record=record,
                        target_draw_number=target.draw_number,
                        status=status,
                        reason_code=exc.reason_code,
                    )
                )
                status_counts[status] += 1
                status_counts_by_method[method_id][status] += 1
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
                raise LegacySourceNativeWave29BatchImportError(
                    "ordered-20 construction failed: "
                    f"{constructed.reason.value}"
                )
            executions.append(
                {
                    "candidate_k": None,
                    "combination_count": (
                        native.metadata.source_method_combination_count
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
                    "portfolio_derivation": CONSTRUCTOR_IDENTIFIER,
                    "portfolio_ticket_count": 20,
                    "status": "OK",
                    "strategy_id": record.strategy_id,
                    "strategy_version": record.strategy_version,
                    "target_draw_number": target.draw_number,
                }
            )
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
            f"legacy-biglotto-source-native-wave29-"
            f"{pinned_history.database_sha256_before[:12]}"
        ),
        "dataset_sha256": pinned_history.database_sha256_before,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "candidate_k_semantics": (
                "NULL_NO_SOURCE_CANDIDATE_POOL_DISTINCT_FROM_NATIVE_TICKETS"
            ),
            "combination_count": dict(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD
            ),
            "combination_count_semantics": (
                "SOURCE_PREDICTOR_CONFIGURATION_COUNT_DISTINCT_FROM_"
                "CANDIDATE_K_NATIVE_TICKET_COUNT_AND_ORDERED20_COUNT"
            ),
            "combination_members": dict(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE29_METHOD
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
                method_id: dict(
                    sorted(status_counts_by_method[method_id].items())
                )
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS
            },
            "frozen_sources": {
                method_id: (
                    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE29_METHOD[method_id]
                )
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE29_METHODS
            },
            "frozen_support_artifacts": dict(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE29_METHOD
            ),
            "minimum_history_draws": dict(
                MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE29_METHOD
            ),
            "native_ticket_count": dict(
                NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE29_METHOD
            ),
            "native_ticket_semantics": dict(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE29_METHOD
            ),
            "random_protocols": dict(
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE29_METHOD
            ),
            "replay_truth_supplemented_draw_count": (
                pinned_history.replay_truth_supplemented_draw_count
            ),
            "source_history_order": dict(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE29_METHOD
            ),
            "source_history_order_detail": dict(
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE29_METHOD
            ),
            "source_native_protocol": SOURCE_NATIVE_WAVE29_PROTOCOL,
            "source_read_mode": "sqlite-mode=ro,immutable=1,query_only=ON",
            "user_seed": user_seed,
        },
        "targets": targets,
    }


__all__ = [
    "MATERIALIZATION_SCHEMA_VERSION",
    "LegacySourceNativeWave29BatchImportError",
    "materialize_legacy_source_native_wave29_batch",
]
