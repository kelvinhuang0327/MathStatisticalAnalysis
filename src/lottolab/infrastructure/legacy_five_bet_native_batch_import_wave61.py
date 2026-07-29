"""Causal materialization for the wave-61 five-bet closed results."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from lottolab.application.biglotto_multi_ticket_backtest import (
    INPUT_SCHEMA_VERSION,
)
from lottolab.application.legacy_five_bet_native_portfolios_wave61 import (
    CAUSAL_ELIGIBILITY_RULE,
    CAUSAL_PROTOCOL,
    CONTEXT_POLICY,
    DEFAULT_SOURCE_NATIVE_WAVE61_USER_SEED,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    METHOD_ID,
    MODEL_CANDIDATE_K,
    NATIVE_TICKET_SEMANTICS,
    PINNED_DATASET_SHA256,
    SOURCE_NATIVE_WAVE61_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256,
    LegacyFiveBetNativeWave61Request,
    LegacyFiveBetNativeWave61SourceError,
    generate_legacy_five_bet_native_wave61_portfolio,
    load_legacy_five_bet_native_wave61_ledger_for_verification,
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
    PinnedBigLottoHistory,
    ReplayBatchImportError,
    load_pinned_biglotto_history,
)

MATERIALIZATION_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_FIVE_BET_NATIVE_WAVE61_BATCH_V1"
)


class LegacyFiveBetNativeWave61BatchImportError(ValueError):
    """The pinned dataset or wave-61 ledger violates the batch contract."""


def _validate_logical_dataset_identity(
    pinned_history: PinnedBigLottoHistory,
    causal_history: tuple[LegacyHistoryDraw, ...],
) -> str:
    physical_sha256 = pinned_history.database_sha256_before
    if physical_sha256 == PINNED_DATASET_SHA256:
        return PINNED_DATASET_SHA256
    ledger = load_legacy_five_bet_native_wave61_ledger_for_verification()
    if (
        len(pinned_history.draws) != 2149
        or tuple(
            draw.draw_number for draw in pinned_history.draws
        )
        != ledger.targets
        or pinned_history.database_sha256_after != physical_sha256
    ):
        raise LegacyFiveBetNativeWave61BatchImportError(
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
        raise LegacyFiveBetNativeWave61BatchImportError(
            "regeneration database leaves the pinned logical history"
        )
    return PINNED_DATASET_SHA256


def _catalog_record() -> FullStrategyCatalogRecord:
    by_method = {
        record.legacy_method_id: record
        for record in load_full_strategy_catalog().records
    }
    record = by_method.get(METHOD_ID)
    if record is None or record.source_sha256 != SOURCE_SHA256:
        raise LegacyFiveBetNativeWave61BatchImportError(
            "frozen wave-61 catalog identity changed"
        )
    return record


def _closed_status(reason_code: str) -> str:
    if reason_code.startswith("FROZEN_SOURCE_EXECUTION_ERROR:"):
        return "CLOSED_EXECUTION_ERROR"
    return "CLOSED_REJECTED"


def materialize_legacy_five_bet_native_wave61_batch(
    *,
    database: Path,
    expected_database_sha256: str,
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE61_USER_SEED,
) -> dict[str, object]:
    """Build source-horizon closed rows and causal ordered-20 rows."""

    try:
        pinned_history = load_pinned_biglotto_history(
            database=database,
            expected_database_sha256=expected_database_sha256,
        )
    except ReplayBatchImportError as exc:
        raise LegacyFiveBetNativeWave61BatchImportError(
            str(exc)
        ) from exc
    record = _catalog_record()
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
    status_counts: Counter[str] = Counter()
    native_counts: Counter[int] = Counter()
    configuration_counts: Counter[int] = Counter()
    for target_index, target in enumerate(pinned_history.draws):
        try:
            native = generate_legacy_five_bet_native_wave61_portfolio(
                LegacyFiveBetNativeWave61Request(
                    target_draw_number=target.draw_number,
                    target_draw_date=target.draw_date,
                    history=causal_history[:target_index],
                    dataset_sha256=logical_dataset_sha256,
                    replicate_id=0,
                    user_seed=user_seed,
                )
            )
        except LegacyFiveBetNativeWave61SourceError as exc:
            status = _closed_status(exc.reason_code)
            executions.append(
                {
                    "reason_code": exc.reason_code,
                    "status": status,
                    "strategy_id": record.strategy_id,
                    "strategy_version": record.strategy_version,
                    "target_draw_number": target.draw_number,
                }
            )
            status_counts[status] += 1
            continue
        if target_index == 0:
            raise LegacyFiveBetNativeWave61BatchImportError(
                "executable wave-61 target has no causal cutoff"
            )
        cutoff = pinned_history.draws[target_index - 1]
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
            raise LegacyFiveBetNativeWave61BatchImportError(
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
        status_counts["OK"] += 1
        native_counts[len(native.tickets)] += 1
        configuration_counts[
            native.metadata.local_configuration_count
        ] += 1
    return {
        "dataset_id": (
            f"legacy-biglotto-five-bet-native-wave61-"
            f"{logical_dataset_sha256[:12]}"
        ),
        "dataset_sha256": logical_dataset_sha256,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "candidate_k": MODEL_CANDIDATE_K,
            "candidate_k_semantics": (
                "FULL_49_LEGAL_NUMBER_DOMAIN_FOR_ORDERED20_INPUT_"
                "DISTINCT_FROM_SOURCE_CANDIDATE_POOLS_NATIVE_TICKET_"
                "COUNT_LOCAL_CONFIGURATION_COUNT_AND_ORDERED20_COUNT"
            ),
            "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
            "causal_protocol": CAUSAL_PROTOCOL,
            "combination_count_distribution": dict(
                sorted(configuration_counts.items())
            ),
            "combination_count_semantics": (
                "EXECUTED_SOURCE_MAIN_CONFIGURATION_COUNT_DISTINCT_"
                "FROM_CANDIDATE_K_NATIVE_TICKET_COUNT_AND_ORDERED20_COUNT"
            ),
            "constructor": CONSTRUCTOR_IDENTIFIER,
            "context_policy": CONTEXT_POLICY,
            "database_sha256_after": pinned_history.database_sha256_after,
            "database_sha256_before": (
                pinned_history.database_sha256_before
            ),
            "execution_status_counts": dict(
                sorted(status_counts.items())
            ),
            "frozen_source": {METHOD_ID: SOURCE_SHA256},
            "ledger_content_sha256": LEDGER_CONTENT_SHA256,
            "ledger_file_sha256": LEDGER_FILE_SHA256,
            "ledger_schema_version": LEDGER_SCHEMA_VERSION,
            "logical_dataset_sha256": logical_dataset_sha256,
            "native_ticket_count_distribution": dict(
                sorted(native_counts.items())
            ),
            "native_ticket_semantics": NATIVE_TICKET_SEMANTICS,
            "random_protocol": (
                "SOURCE_RUN_BENCHMARK_SEED42_PER_DECLARED_HORIZON_RUN"
            ),
            "replay_truth_supplemented_draw_count": (
                pinned_history.replay_truth_supplemented_draw_count
            ),
            "source_candidate_k_values": [18, 20, 49],
            "source_closed_result_horizons": [150, 200],
            "source_history_order": "OLDEST_FIRST",
            "source_native_protocol": SOURCE_NATIVE_WAVE61_PROTOCOL,
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
    "LegacyFiveBetNativeWave61BatchImportError",
    "materialize_legacy_five_bet_native_wave61_batch",
]
