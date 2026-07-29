"""Causal materialization for the wave-47 frozen source-grid batch."""

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
from lottolab.application.legacy_source_grid_native_portfolios_wave47 import (
    CONTEXT_POLICY,
    DEFAULT_SOURCE_NATIVE_WAVE47_USER_SEED,
    FROZEN_SOURCE_COMMIT,
    INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE47_METHOD,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE47_METHOD,
    MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE47_METHOD,
    MODEL_CANDIDATE_K,
    NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD,
    NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE47_METHOD,
    PINNED_DATASET_SHA256,
    SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE47_METHOD,
    SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD,
    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE47_METHOD,
    SOURCE_NATIVE_WAVE47_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE47_METHOD,
    STABILITY_ALIAS_METHOD_ID,
    STABILITY_ALIAS_TARGET_METHOD_ID,
    SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS,
    LegacySourceGridNativeWave47Request,
    generate_legacy_source_grid_native_wave47_portfolio,
    load_legacy_source_grid_native_wave47_ledger_for_verification,
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

MATERIALIZATION_SCHEMA_VERSION = "BIG_LOTTO_LEGACY_SOURCE_GRID_NATIVE_WAVE47_BATCH_V1"
CLOSED_REASON = "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"


class LegacySourceGridNativeWave47BatchImportError(ValueError):
    """The pinned dataset or source ledger violates the batch contract."""


def _validate_logical_dataset_identity(
    pinned_history: PinnedBigLottoHistory,
    causal_history: tuple[LegacyHistoryDraw, ...],
) -> str:
    physical_sha256 = pinned_history.database_sha256_before
    if physical_sha256 == PINNED_DATASET_SHA256:
        return PINNED_DATASET_SHA256
    ledger = load_legacy_source_grid_native_wave47_ledger_for_verification()
    draws = pinned_history.draws
    target_draw_numbers = tuple(draw.draw_number for draw in draws[1:])
    if (
        len(draws) != 2149
        or target_draw_numbers != ledger.targets
        or pinned_history.database_sha256_after != physical_sha256
    ):
        raise LegacySourceGridNativeWave47BatchImportError(
            "regeneration database leaves the pinned logical target sequence"
        )
    contexts = tuple(
        hashlib.sha256(
            json.dumps(
                [list(draw.numbers) for draw in causal_history[:target_index]],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        for target_index in range(1, len(causal_history))
    )
    if contexts != ledger.context_sha256:
        raise LegacySourceGridNativeWave47BatchImportError(
            "regeneration database leaves the pinned logical history"
        )
    return PINNED_DATASET_SHA256


def _catalog_records() -> dict[str, FullStrategyCatalogRecord]:
    by_method = {record.legacy_method_id: record for record in load_full_strategy_catalog().records}
    records: dict[str, FullStrategyCatalogRecord] = {}
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS:
        record = by_method.get(method_id)
        if (
            record is None
            or record.source_sha256 != SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
        ):
            raise LegacySourceGridNativeWave47BatchImportError(
                "frozen source-grid wave-47 catalog identity changed"
            )
        records[method_id] = record
    return records


def materialize_legacy_source_grid_native_wave47_batch(
    *,
    database: Path,
    expected_database_sha256: str,
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE47_USER_SEED,
) -> dict[str, object]:
    """Build ordered-20 evaluator input for seven executable source rows."""

    try:
        pinned_history = load_pinned_biglotto_history(
            database=database,
            expected_database_sha256=expected_database_sha256,
        )
    except ReplayBatchImportError as exc:
        raise LegacySourceGridNativeWave47BatchImportError(str(exc)) from exc
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
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS:
        record = records[method_id]
        minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
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
            native = generate_legacy_source_grid_native_wave47_portfolio(
                LegacySourceGridNativeWave47Request(
                    legacy_method_id=method_id,
                    target_draw_number=target.draw_number,
                    history=prior_history,
                    dataset_sha256=logical_dataset_sha256,
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
                raise LegacySourceGridNativeWave47BatchImportError(
                    f"ordered-20 construction failed: {constructed.reason.value}"
                )
            executions.append(
                {
                    "candidate_k": MODEL_CANDIDATE_K,
                    "combination_count": (
                        SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
                    ),
                    "history_cutoff_draw_date": cutoff.draw_date.isoformat(),
                    "history_cutoff_draw_number": cutoff.draw_number,
                    "native_generation": native.metadata.canonical_dict(),
                    "native_ticket_count": len(native.tickets),
                    "native_tickets": [list(ticket) for ticket in native.tickets],
                    "ordered_portfolio": [list(ticket) for ticket in constructed.tickets],
                    "ordered_portfolio_derivation": (constructed.metadata.canonical_dict()),
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
        "dataset_id": (f"legacy-biglotto-source-grid-native-wave47-{logical_dataset_sha256[:12]}"),
        "dataset_sha256": logical_dataset_sha256,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "alias_disposition": {
                "alias_method": STABILITY_ALIAS_METHOD_ID,
                "canonical_method": STABILITY_ALIAS_TARGET_METHOD_ID,
                "output_mismatch_count": 0,
                "overlapping_causal_output_case_count": 1649,
            },
            "candidate_k": {
                method_id: MODEL_CANDIDATE_K for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
            },
            "candidate_k_semantics": (
                "FULL_49_LEGAL_NUMBER_DOMAIN_FOR_ORDERED20_INPUT_DISTINCT_"
                "FROM_SOURCE_INTERNAL_CANDIDATE_POOL_NATIVE_TICKET_COUNT_"
                "SOURCE_CONFIGURATION_COUNT_AND_ORDERED20_COUNT"
            ),
            "constructor": CONSTRUCTOR_IDENTIFIER,
            "context_policy": CONTEXT_POLICY,
            "database_sha256_after": pinned_history.database_sha256_after,
            "database_sha256_before": pinned_history.database_sha256_before,
            "execution_status_counts": dict(sorted(aggregate_status_counts.items())),
            "execution_status_counts_by_method": status_counts_by_method,
            "frozen_source_commit": FROZEN_SOURCE_COMMIT,
            "frozen_sources": {
                method_id: SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
            },
            "intra_ticket_order_semantics": {
                method_id: (INTRA_TICKET_ORDER_SEMANTICS_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id])
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
            },
            "ledger_content_sha256": LEDGER_CONTENT_SHA256,
            "ledger_file_sha256": LEDGER_FILE_SHA256,
            "ledger_schema_version": LEDGER_SCHEMA_VERSION,
            "logical_dataset_sha256": logical_dataset_sha256,
            "logical_history_anchor": ("CHECKSUMMED_WAVE47_FULL_PREFIX_CONTEXT_LEDGER"),
            "minimum_history_draws": {
                method_id: (MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id])
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
            },
            "minimum_history_rationale": {
                method_id: (MINIMUM_HISTORY_RATIONALE_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id])
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
            },
            "native_ticket_count": {
                method_id: (NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id])
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
            },
            "native_ticket_semantics": {
                method_id: (NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id])
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
            },
            "random_protocols": {
                method_id: "NONE_DETERMINISTIC_FROZEN_SOURCE"
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
            },
            "replay_truth_supplemented_draw_count": (
                pinned_history.replay_truth_supplemented_draw_count
            ),
            "source_candidate_k_values": {
                method_id: list(SOURCE_CANDIDATE_K_VALUES_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id])
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
            },
            "source_configuration_count": {
                method_id: (SOURCE_CONFIGURATION_COUNT_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id])
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
            },
            "source_configuration_count_semantics": (
                "DECLARED_LOCAL_STRATEGY_CONFIGURATIONS_DISTINCT_FROM_"
                "CANDIDATE_K_NATIVE_TICKET_COUNT_AND_ORDERED20_COUNT"
            ),
            "source_configuration_members": {
                method_id: list(
                    SOURCE_CONFIGURATION_MEMBERS_BY_SOURCE_NATIVE_WAVE47_METHOD[method_id]
                )
                for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
            },
            "source_history_order": {
                method_id: "OLDEST_FIRST" for method_id in SUPPORTED_SOURCE_NATIVE_WAVE47_METHODS
            },
            "source_native_protocol": SOURCE_NATIVE_WAVE47_PROTOCOL,
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
    "CLOSED_REASON",
    "MATERIALIZATION_SCHEMA_VERSION",
    "LegacySourceGridNativeWave47BatchImportError",
    "materialize_legacy_source_grid_native_wave47_batch",
]
