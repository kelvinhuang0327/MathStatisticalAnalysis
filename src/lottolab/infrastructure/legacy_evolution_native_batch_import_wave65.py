"""Causal materialization for the frozen wave-65 evolution engine."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, cast

from lottolab.application.biglotto_multi_ticket_backtest import (
    INPUT_SCHEMA_VERSION,
)
from lottolab.application.legacy_evolution_native_portfolios_wave65 import (
    ACCELERATION_PROTOCOL,
    CAUSAL_ELIGIBILITY_RULE,
    CAUSAL_PROTOCOL,
    CLOSED_REASON,
    CONTEXT_POLICY,
    DEFAULT_SOURCE_NATIVE_WAVE65_USER_SEED,
    DETERMINISM_PROTOCOL,
    DRIVER_GENERATIONS,
    DRIVER_N_TEST,
    DRIVER_POPULATION_SIZE,
    ENGINE_SEED,
    EXPECTED_NATIVE_DUPLICATE_DISTRIBUTION,
    EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTION,
    FIRST_EXECUTABLE_TARGET_INDEX,
    LEADERBOARD_SEQUENCE_SHA256,
    LEDGER_CONTENT_SHA256,
    LEDGER_FILE_SHA256,
    LEDGER_SCHEMA_VERSION,
    METHOD_ID,
    NATIVE_TICKET_ORDER,
    NATIVE_TICKET_SEMANTICS,
    PINNED_DATASET_SHA256,
    SOURCE_NATIVE_WAVE65_PROTOCOL,
    SOURCE_REFERENCE_RUNTIME,
    SOURCE_SHA256,
    TICKET_SEQUENCE_SHA256,
    LegacyEvolutionNativeWave65Request,
    LegacyEvolutionNativeWave65SourceError,
    generate_legacy_evolution_native_wave65_portfolio,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_xgboost_native_portfolios_wave64 import (
    LEDGER_CONTENT_SHA256 as WAVE64_LEDGER_CONTENT_SHA256,
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
    PinnedBigLottoDraw,
)

MATERIALIZATION_SCHEMA_VERSION = (
    "BIG_LOTTO_LEGACY_EVOLUTION_NATIVE_WAVE65_BATCH_V1"
)
HISTORY_INPUT_FILE_SHA256 = (
    "25ba060686325f72ba6a89d9528243f499e378f494cf055a52c2992943628480"
)
HISTORY_INPUT_CANONICAL_SHA256 = (
    "477d8597fe76104bcd7abcece88a258a51d04b4de801d7afaba133d6e1da038a"
)


class LegacyEvolutionNativeWave65BatchImportError(ValueError):
    """The pinned history input or evolution ledger violates its contract."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")



def _parse_date(value: object, context: str) -> date:
    if type(value) is not str:
        raise LegacyEvolutionNativeWave65BatchImportError(
            f"{context}: date is missing"
        )
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise LegacyEvolutionNativeWave65BatchImportError(
            f"{context}: date is invalid"
        ) from exc


def _parse_ticket(
    value: object,
    context: str,
) -> tuple[int, int, int, int, int, int]:
    if not isinstance(value, list):
        raise LegacyEvolutionNativeWave65BatchImportError(
            f"{context}: ticket is missing"
        )
    items = cast(list[object], value)
    if len(items) != 6 or any(type(number) is not int for number in items):
        raise LegacyEvolutionNativeWave65BatchImportError(
            f"{context}: ticket must contain six integers"
        )
    numbers = cast(list[int], items)
    ticket = tuple(numbers)
    if (
        numbers != sorted(numbers)
        or len(set(numbers)) != 6
        or any(not 1 <= number <= 49 for number in numbers)
    ):
        raise LegacyEvolutionNativeWave65BatchImportError(
            f"{context}: ticket is not canonical"
        )
    return cast(tuple[int, int, int, int, int, int], ticket)


def _load_history_input(
    path: Path,
) -> tuple[tuple[PinnedBigLottoDraw, ...], str]:
    if path.is_symlink() or not path.is_file():
        raise LegacyEvolutionNativeWave65BatchImportError(
            "history input must be a regular non-symlink file"
        )
    raw = path.read_bytes()
    physical_sha256 = hashlib.sha256(raw).hexdigest()
    if physical_sha256 != HISTORY_INPUT_FILE_SHA256:
        raise LegacyEvolutionNativeWave65BatchImportError(
            "history input physical SHA-256 changed"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacyEvolutionNativeWave65BatchImportError(
            "history input is invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise LegacyEvolutionNativeWave65BatchImportError(
            "history input must be an object"
        )
    document = cast(dict[str, Any], parsed)
    provenance = document.get("source_provenance")
    if (
        document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("lottery_type") != "BIG_LOTTO"
        or hashlib.sha256(_canonical_bytes(document)).hexdigest()
        != HISTORY_INPUT_CANONICAL_SHA256
        or not isinstance(provenance, dict)
        or cast(dict[str, object], provenance).get(
            "ledger_content_sha256"
        )
        != WAVE64_LEDGER_CONTENT_SHA256
    ):
        raise LegacyEvolutionNativeWave65BatchImportError(
            "history input authority changed"
        )
    targets_raw = document.get("targets")
    if not isinstance(targets_raw, list):
        raise LegacyEvolutionNativeWave65BatchImportError(
            "history input targets are missing"
        )
    draws: list[PinnedBigLottoDraw] = []
    for candidate in cast(list[object], targets_raw):
        if not isinstance(candidate, dict):
            raise LegacyEvolutionNativeWave65BatchImportError(
                "history input target is invalid"
            )
        target = cast(dict[str, object], candidate)
        draw_number = target.get("draw_number")
        special = target.get("winning_special_number")
        if type(draw_number) is not str or type(special) is not int:
            raise LegacyEvolutionNativeWave65BatchImportError(
                "history input target identity changed"
            )
        draws.append(
            PinnedBigLottoDraw(
                draw_number=draw_number,
                draw_date=_parse_date(
                    target.get("draw_date"),
                    f"draw {draw_number}",
                ),
                numbers=_parse_ticket(
                    target.get("winning_main_numbers"),
                    f"draw {draw_number}",
                ),
                special=special,
            )
        )
    if (
        len(draws) != 2149
        or draws[0].draw_number != "96000001"
        or draws[-1].draw_number != "115000073"
        or len({draw.draw_number for draw in draws}) != len(draws)
        or len({draw.draw_date for draw in draws}) != len(draws)
    ):
        raise LegacyEvolutionNativeWave65BatchImportError(
            "wave-65 target set changed"
        )
    return tuple(draws), physical_sha256


def _catalog_record() -> FullStrategyCatalogRecord:
    by_method = {
        record.legacy_method_id: record
        for record in load_full_strategy_catalog().records
    }
    record = by_method.get(METHOD_ID)
    if record is None or record.source_sha256 != SOURCE_SHA256:
        raise LegacyEvolutionNativeWave65BatchImportError(
            "frozen wave-65 catalog identity changed"
        )
    return record


def materialize_legacy_evolution_native_wave65_batch(
    *,
    history_input: Path,
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE65_USER_SEED,
) -> dict[str, object]:
    """Build source-closed rows and one ordered-20 per executable target."""

    draws, history_input_file_sha256 = _load_history_input(history_input)
    record = _catalog_record()
    causal_history = tuple(
        LegacyHistoryDraw(
            draw_number=draw.draw_number,
            numbers=draw.numbers,
        )
        for draw in draws
    )
    executions: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    native_ticket_counts: Counter[int] = Counter()
    duplicate_counts: Counter[int] = Counter()
    total_tested_values: list[int] = []
    for target_index, target in enumerate(draws):
        try:
            native = generate_legacy_evolution_native_wave65_portfolio(
                LegacyEvolutionNativeWave65Request(
                    target_draw_number=target.draw_number,
                    target_draw_date=target.draw_date,
                    history=causal_history[:target_index],
                    dataset_sha256=PINNED_DATASET_SHA256,
                    replicate_id=0,
                    user_seed=user_seed,
                )
            )
        except LegacyEvolutionNativeWave65SourceError as exc:
            if exc.reason_code != CLOSED_REASON:
                raise LegacyEvolutionNativeWave65BatchImportError(
                    "unexpected wave-65 source closure"
                ) from exc
            closed: dict[str, object] = {
                "reason_code": exc.reason_code,
                "status": "CLOSED_INSUFFICIENT_HISTORY",
                "strategy_id": record.strategy_id,
                "strategy_version": record.strategy_version,
                "target_draw_number": target.draw_number,
            }
            if target_index:
                cutoff = draws[target_index - 1]
                closed.update(
                    {
                        "history_cutoff_draw_date": (
                            cutoff.draw_date.isoformat()
                        ),
                        "history_cutoff_draw_number": (
                            cutoff.draw_number
                        ),
                    }
                )
            executions.append(closed)
            status_counts["CLOSED_INSUFFICIENT_HISTORY"] += 1
            continue
        if target_index == 0:
            raise LegacyEvolutionNativeWave65BatchImportError(
                "executable wave-65 target has no causal cutoff"
            )
        cutoff = draws[target_index - 1]
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
            raise LegacyEvolutionNativeWave65BatchImportError(
                "ordered-20 construction failed: "
                f"{constructed.reason.value}"
            )
        executions.append(
            {
                "candidate_k": None,
                "combination_count": None,
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
        native_ticket_counts[len(native.tickets)] += 1
        duplicate_counts[
            native.metadata.native_duplicate_ticket_count
        ] += 1
        total_tested_values.append(
            native.metadata.total_strategies_tested
        )
    expected_status_counts = Counter(
        {
            "CLOSED_INSUFFICIENT_HISTORY": min(
                FIRST_EXECUTABLE_TARGET_INDEX,
                len(draws),
            ),
            "OK": max(
                0,
                len(draws) - FIRST_EXECUTABLE_TARGET_INDEX,
            ),
        }
    )
    if status_counts != expected_status_counts:
        raise LegacyEvolutionNativeWave65BatchImportError(
            "wave-65 execution coverage changed"
        )
    if len(draws) == 2149 and (
        {
            str(key): value
            for key, value in sorted(native_ticket_counts.items())
        }
        != EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTION
        or {
            str(key): value
            for key, value in sorted(duplicate_counts.items())
        }
        != EXPECTED_NATIVE_DUPLICATE_DISTRIBUTION
        or sum(
            count * occurrences
            for count, occurrences in native_ticket_counts.items()
        )
        != 12959
    ):
        raise LegacyEvolutionNativeWave65BatchImportError(
            "wave-65 native ticket distribution changed"
        )
    return {
        "dataset_id": (
            "legacy-biglotto-evolution-native-wave65-"
            f"{PINNED_DATASET_SHA256[:12]}"
        ),
        "dataset_sha256": PINNED_DATASET_SHA256,
        "dataset_version": MATERIALIZATION_SCHEMA_VERSION,
        "executions": executions,
        "lottery_type": "BIG_LOTTO",
        "schema_version": INPUT_SCHEMA_VERSION,
        "source_provenance": {
            "acceleration_protocol": ACCELERATION_PROTOCOL,
            "candidate_k": None,
            "candidate_k_semantics": (
                "NOT_USED_BY_SOURCE_EVOLUTION_ENGINE_DISTINCT_FROM_"
                "POPULATION_SIZE_NATIVE_TICKET_COUNT_AND_ORDERED20_COUNT"
            ),
            "causal_eligibility_rule": CAUSAL_ELIGIBILITY_RULE,
            "causal_protocol": CAUSAL_PROTOCOL,
            "combination_count": None,
            "combination_count_semantics": (
                "NOT_USED_BY_SOURCE_EVOLUTION_ENGINE_DISTINCT_FROM_"
                "STRATEGIES_TESTED_NATIVE_TICKET_COUNT_AND_ORDERED20_COUNT"
            ),
            "constructor": CONSTRUCTOR_IDENTIFIER,
            "context_policy": CONTEXT_POLICY,
            "determinism_protocol": DETERMINISM_PROTOCOL,
            "driver_generations": DRIVER_GENERATIONS,
            "driver_n_test": DRIVER_N_TEST,
            "driver_population_size": DRIVER_POPULATION_SIZE,
            "engine_seed": ENGINE_SEED,
            "execution_status_counts": dict(
                sorted(status_counts.items())
            ),
            "frozen_source": {METHOD_ID: SOURCE_SHA256},
            "history_input_canonical_sha256": (
                HISTORY_INPUT_CANONICAL_SHA256
            ),
            "history_input_file_sha256": history_input_file_sha256,
            "leaderboard_sequence_sha256": (
                LEADERBOARD_SEQUENCE_SHA256
            ),
            "ledger_content_sha256": LEDGER_CONTENT_SHA256,
            "ledger_file_sha256": LEDGER_FILE_SHA256,
            "ledger_schema_version": LEDGER_SCHEMA_VERSION,
            "logical_dataset_sha256": PINNED_DATASET_SHA256,
            "native_duplicate_ticket_count_distribution": {
                str(key): value
                for key, value in sorted(duplicate_counts.items())
            },
            "native_ticket_count_distribution": {
                str(key): value
                for key, value in sorted(native_ticket_counts.items())
            },
            "native_ticket_order": NATIVE_TICKET_ORDER,
            "native_ticket_position_count": sum(
                count * occurrences
                for count, occurrences in native_ticket_counts.items()
            ),
            "native_ticket_semantics": NATIVE_TICKET_SEMANTICS,
            "source_history_order": "OLDEST_FIRST",
            "source_native_protocol": SOURCE_NATIVE_WAVE65_PROTOCOL,
            "source_random_state_explicit": True,
            "source_reference_runtime": SOURCE_REFERENCE_RUNTIME,
            "source_read_mode": (
                "CHECKSUM_PINNED_WAVE64_MATERIALIZED_TARGET_TRUTHS"
            ),
            "ticket_sequence_sha256": TICKET_SEQUENCE_SHA256,
            "total_strategies_tested_max": (
                max(total_tested_values) if total_tested_values else None
            ),
            "total_strategies_tested_min": (
                min(total_tested_values) if total_tested_values else None
            ),
            "upstream_wave64_ledger_content_sha256": (
                WAVE64_LEDGER_CONTENT_SHA256
            ),
            "user_seed": user_seed,
        },
        "targets": [
            {
                "draw_date": draw.draw_date.isoformat(),
                "draw_number": draw.draw_number,
                "winning_main_numbers": list(draw.numbers),
                "winning_special_number": draw.special,
            }
            for draw in draws
        ],
    }


__all__ = [
    "HISTORY_INPUT_CANONICAL_SHA256",
    "HISTORY_INPUT_FILE_SHA256",
    "MATERIALIZATION_SCHEMA_VERSION",
    "LegacyEvolutionNativeWave65BatchImportError",
    "materialize_legacy_evolution_native_wave65_batch",
]
