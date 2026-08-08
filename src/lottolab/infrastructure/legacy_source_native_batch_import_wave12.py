"""Causal materialization for the twelfth frozen source-native batch."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from lottolab.application.biglotto_multi_ticket_backtest import INPUT_SCHEMA_VERSION
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_source_native_portfolios_wave12 import (
    CANDIDATE_K_BY_SOURCE_NATIVE_WAVE12_METHOD,
    DEFAULT_SOURCE_NATIVE_WAVE12_USER_SEED,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE12_METHOD,
    MODERATE_SELECTION_METHOD_ID,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE12_METHOD,
    RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE12_METHOD,
    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE12_METHOD,
    SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE12_METHOD,
    SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE12_METHOD,
    SOURCE_NATIVE_WAVE12_PROTOCOL,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD,
    LegacySourceNativeWave12Request,
    LegacySourceNativeWave12SourceError,
    generate_legacy_source_native_wave12_portfolio,
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
    "BIG_LOTTO_LEGACY_SOURCE_NATIVE_WAVE12_BATCH_V1"
)


class LegacySourceNativeWave12BatchImportError(ValueError):
    """The source DB or frozen strategy cannot satisfy this batch contract."""


def _catalog_record() -> FullStrategyCatalogRecord:
    catalog = load_full_strategy_catalog()
    try:
        record = next(
            record
            for record in catalog.records
            if record.legacy_method_id == MODERATE_SELECTION_METHOD_ID
        )
    except StopIteration as exc:
        raise LegacySourceNativeWave12BatchImportError(
            "frozen source-native wave-12 catalog identity changed"
        ) from exc
    if record.source_sha256 != (
        SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD[
            MODERATE_SELECTION_METHOD_ID
        ]
    ):
        raise LegacySourceNativeWave12BatchImportError(
            "frozen source-native wave-12 catalog identity changed"
        )
    return record


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


def materialize_legacy_source_native_wave12_batch(
    *,
    database: Path,
    expected_database_sha256: str,
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE12_USER_SEED,
) -> dict[str, object]:
    """Build ordered-20 evaluator input for the 180-grid method."""

    try:
        pinned_history = load_pinned_biglotto_history(
            database=database,
            expected_database_sha256=expected_database_sha256,
            require_replay_authority=False,
        )
    except ReplayBatchImportError as exc:
        raise LegacySourceNativeWave12BatchImportError(str(exc)) from exc
    record = _catalog_record()
    causal_history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in pinned_history.draws
    )
    executions: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE12_METHOD[
        MODERATE_SELECTION_METHOD_ID
    ]

    for target_index, target in enumerate(pinned_history.draws):
        prior_history = causal_history[:target_index]
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
            continue

        cutoff = pinned_history.draws[target_index - 1]
        try:
            native = generate_legacy_source_native_wave12_portfolio(
                LegacySourceNativeWave12Request(
                    legacy_method_id=MODERATE_SELECTION_METHOD_ID,
                    target_draw_number=target.draw_number,
                    history=prior_history,
                    replicate_id=0,
                    user_seed=user_seed,
                )
            )
        except LegacySourceNativeWave12SourceError as exc:
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
            raise LegacySourceNativeWave12BatchImportError(
                "ordered-20 construction failed: "
                f"{constructed.reason.value}"
            )
        executions.append(
            {
                "combination_count": (
                    SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE12_METHOD[
                        MODERATE_SELECTION_METHOD_ID
                    ]
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
            f"legacy-biglotto-source-native-wave12-"
            f"{pinned_history.database_sha256_before[:12]}"
        ),
        "dataset_sha256": pinned_history.database_sha256_before,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "candidate_k": dict(
                CANDIDATE_K_BY_SOURCE_NATIVE_WAVE12_METHOD
            ),
            "candidate_k_semantics": (
                "NOT_APPLICABLE; FROZEN_GRID_PARAMETERS_ARE_"
                "CONFIGURATIONS_NOT_CANDIDATE_POOLS"
            ),
            "combination_count": dict(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE12_METHOD
            ),
            "combination_count_semantics": (
                "FROZEN_PARAMETER_GRID_CONFIGURATION_COUNT"
            ),
            "combination_members": dict(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE12_METHOD
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
                MODERATE_SELECTION_METHOD_ID: dict(
                    sorted(status_counts.items())
                )
            },
            "frozen_sources": dict(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE12_METHOD
            ),
            "minimum_history_draws": dict(
                MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE12_METHOD
            ),
            "native_ticket_semantics": dict(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE12_METHOD
            ),
            "random_protocols": dict(
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE12_METHOD
            ),
            "replay_truth_supplemented_draw_count": (
                pinned_history.replay_truth_supplemented_draw_count
            ),
            "source_history_order": dict(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE12_METHOD
            ),
            "source_native_protocol": SOURCE_NATIVE_WAVE12_PROTOCOL,
            "source_read_mode": (
                "sqlite-mode=ro,immutable=1,query_only=ON"
            ),
            "source_result_selection": (
                "NO_TARGET_OUTCOME_GRID_WINNER_SELECTION; ALL_180_"
                "FIXED_CONFIGURATIONS_RETAINED_IN_SOURCE_ORDER"
            ),
            "user_seed": user_seed,
        },
        "targets": targets,
    }


__all__ = [
    "MATERIALIZATION_SCHEMA_VERSION",
    "LegacySourceNativeWave12BatchImportError",
    "materialize_legacy_source_native_wave12_batch",
]
