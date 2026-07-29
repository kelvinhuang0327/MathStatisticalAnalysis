"""Checksummed frozen evolution-engine native-ticket replay for wave 65."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from functools import lru_cache
from importlib.resources import files
from types import MappingProxyType
from typing import Any, cast

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

METHOD_ID = "tools/evolving_strategy_engine/evolution_engine.py"
SOURCE_SHA256 = (
    "3df019c31ce48e38efc7fd8b52d3e6eb5fd6ab1927bc789785e6d1e85c794f54"
)
SOURCE_NATIVE_WAVE65_PROTOCOL = "legacy_evolution_native_wave65/v1"
CAUSAL_PROTOCOL = (
    "FROZEN_EVOLUTION_ENGINE_SEED42_DRIVER_DEFAULTS_STRICT_PREFIX_V1"
)
ACCELERATION_PROTOCOL = (
    "PURE_BOUNDED_LRU_PREDICT_AND_FEATURE_MEMOIZATION_BY_COMPLETE_"
    "STRATEGY_GRAPH_WITH_WEAK_OBJECT_GRAPH_KEY_CACHE_N_SELECT_AND_"
    "EXACT_INTEGER_PREFIX_PRECOMPUTATION_ON_PINNED_DRAWS_V5"
)
DEFAULT_SOURCE_NATIVE_WAVE65_USER_SEED = (
    "biglotto-full-universe-evolution-native-wave65-v1"
)
FROZEN_SOURCE_COMMIT = "49a25effa62fc24f40789c16be6f11bdfb41a4a9"
PINNED_DATASET_SHA256 = (
    "2f3d711cb97cddabfc6d351b5a639614da60dc3473cc23368711f605e3fe2d6b"
)
LEDGER_RESOURCE_NAME = "biglotto_evolution_wave65_ticket_ledger_v1.json"
LEDGER_SCHEMA_VERSION = "BIG_LOTTO_EVOLUTION_WAVE65_TICKET_LEDGER_V1"
LEDGER_FILE_SHA256 = (
    "3bc4067a0b27cfdf79e9514b4dc578a89b8e454565737dba6c854b23f0a62d1b"
)
LEDGER_CONTENT_SHA256 = (
    "27e73c12ffae5388f112d252e94dedc130322b7124d39129c970575b84455bd3"
)
TICKET_SEQUENCE_SHA256 = (
    "f730565f18f4fe44071f71c0e5f1bfe0159943eab7ae64bee144412caea4bfbe"
)
LEADERBOARD_SEQUENCE_SHA256 = (
    "47f94ca30cb721757cd17a1b2c844aae46829696c2342e0f60eaf930f6bda401"
)
STATUS_SEQUENCE_SHA256 = (
    "dd33670f76e30d69d1f7bb702232696115372b96066ff277e15ef8c1c694af4b"
)
CONTEXT_SEQUENCE_SHA256 = (
    "58987cef166bf6d30fc01df0ea8fa208fb97c124c417cc46e537b82c9b8c3cd9"
)
SOURCE_REFERENCE_RUNTIME = "CPYTHON_3_9_6_NUMPY_1_26_2_SCIPY_1_13_1"
CONTEXT_POLICY = "FULL_STRICT_PREFIX_BEFORE_TARGET"
CAUSAL_ELIGIBILITY_RULE = (
    "TARGET_USES_ONLY_STRICTLY_EARLIER_DRAWS_AND_SOURCE_OOS_"
    "EVALUATOR_REQUIRES_MORE_THAN_500_HISTORY_DRAWS"
)
CLOSED_REASON = "OOS_EVALUATOR_REQUIRES_MORE_THAN_500_HISTORY_DRAWS"
FIRST_EXECUTABLE_TARGET_INDEX = 501
DRIVER_GENERATIONS = 8
DRIVER_POPULATION_SIZE = 50
DRIVER_N_TEST = 1500
ENGINE_SEED = 42
NATIVE_TICKET_SEMANTICS = (
    "FROZEN_SOURCE_REPORT_1_LEADERBOARD_NUMBERS_WITH_ONE_TO_TEN_"
    "NATIVE_TICKET_POSITIONS"
)
NATIVE_TICKET_ORDER = "SOURCE_REPORT_1_LEADERBOARD_ORDER"
DETERMINISM_PROTOCOL = (
    "SOURCE_ENGINE_NUMPY_DEFAULT_RNG_SEED42_DRIVER_GENERATIONS8_"
    "POPULATION50_N_TEST1500_REPEAT_PARITY_PASS"
)
EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTION = {
    "1": 6,
    "2": 8,
    "3": 10,
    "4": 24,
    "5": 187,
    "6": 194,
    "7": 217,
    "8": 277,
    "9": 273,
    "10": 452,
}
EXPECTED_NATIVE_DUPLICATE_DISTRIBUTION = {
    "0": 413,
    "1": 479,
    "2": 352,
    "3": 225,
    "4": 111,
    "5": 46,
    "6": 13,
    "7": 7,
    "8": 2,
}
EXPECTED_SOURCE_ARTIFACTS = (
    (
        "tools/evolving_strategy_engine/evolution_engine.py",
        "ab5455e043fe408c890270340a75e93956fbabc5",
        10504,
        SOURCE_SHA256,
    ),
    (
        "tools/evolving_strategy_engine/strategy_generator.py",
        "426c708927705a0d72e1098b942f8005c805d8c1",
        19698,
        "e63da93ea11ad27e7368f7bd0d9215f371a059353c4c7adde7057fc803444ad6",
    ),
    (
        "tools/evolving_strategy_engine/evaluator.py",
        "f37f0453c855009b8a0584fb8e1d323f121ecdd9",
        4582,
        "f95565da124e506cc5f5045b9136025831bac4dbee2ef8aedf66f177b5cefd34",
    ),
    (
        "tools/evolving_strategy_engine/strategy_base.py",
        "ff72f841c28f8e553d9dddc017b85c2a3ae518dd",
        10543,
        "b9224ce1634482f751223752c7308233a8fd836b9e133facb95458edc85238ea",
    ),
    (
        "tools/evolving_strategy_engine/data_loader.py",
        "5baf194d55ce5de2ad97bbaeffb41780610446cc",
        3292,
        "9a4ba5fd53737cbb7b2c88713c35c3fe4b8c3e7c21c8f2836c5b76a1e9784931",
    ),
    (
        "tools/run_evolution.py",
        "57fe075fdd3594b18a69c919fa7cd6f3c96b9d66",
        3546,
        "0c1d3924493d8350f5d23068b50f29109ef96370026f1dce8711e244995c294f",
    ),
)


class LegacyEvolutionNativeWave65Error(ValueError):
    """A wave-65 request or packaged ledger violates its contract."""


class LegacyEvolutionNativeWave65SourceError(
    LegacyEvolutionNativeWave65Error
):
    """The frozen source has no executable ticket for this target."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacyEvolutionNativeWave65Request:
    target_draw_number: str
    target_draw_date: date
    history: tuple[LegacyHistoryDraw, ...]
    dataset_sha256: str
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE65_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacyEvolutionNativeWave65Metadata:
    protocol: str
    causal_protocol: str
    legacy_method_id: str
    source_sha256: str
    target_draw_number: str
    target_draw_date: str
    replicate_id: int
    user_seed: str | int
    seed_material: str
    seed_digest: str
    determinism_protocol: str
    randomness_used: bool
    source_random_state_explicit: bool
    repeatability_parity_passed: bool
    history_draw_count: int
    history_first_draw_number: str
    history_cutoff_draw_number: str
    source_history_order: str
    source_history_input_draw_count: int
    context_draw_count: int
    context_numbers_sha256: str
    source_candidate_k_values: tuple[int, ...]
    candidate_k: None
    native_ticket_count: int
    native_ticket_count_semantics: str
    native_ticket_order: str
    native_duplicate_ticket_count: int
    combination_count: None
    driver_generations: int
    driver_population_size: int
    driver_n_test: int
    engine_seed: int
    generation_population: tuple[int, ...]
    total_strategies_tested: int
    pattern_exists: bool
    leaderboard: tuple[dict[str, object], ...]
    causal_eligibility_rule: str
    source_reference_runtime: str
    acceleration_protocol: str
    ledger_schema_version: str
    ledger_file_sha256: str
    ledger_content_sha256: str
    ledger_target_index: int

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacyEvolutionNativeWave65Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacyEvolutionNativeWave65Metadata


@dataclass(frozen=True, slots=True)
class _Ledger:
    targets: tuple[str, ...]
    target_index: MappingProxyType[str, int]
    context_sha256: tuple[str, ...]
    history_input_draw_count: tuple[int, ...]
    tickets: tuple[tuple[Ticket, ...] | None, ...]
    leaderboard: tuple[tuple[dict[str, object], ...] | None, ...]
    generation_population: tuple[tuple[int, ...] | None, ...]
    total_strategies_tested: tuple[int | None, ...]
    pattern_exists: tuple[bool | None, ...]
    status: tuple[str, ...]
    closed_reason: tuple[str | None, ...]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _ticket(value: object) -> Ticket:
    if not isinstance(value, list):
        raise LegacyEvolutionNativeWave65Error(
            "packaged wave-65 ticket must be an array"
        )
    values = cast(list[object], value)
    if not all(type(number) is int for number in values):
        raise LegacyEvolutionNativeWave65Error(
            "packaged wave-65 ticket must contain integers"
        )
    integers = cast(list[int], values)
    if (
        len(integers) != 6
        or integers != sorted(integers)
        or len(set(integers)) != 6
        or any(not 1 <= number <= 49 for number in integers)
    ):
        raise LegacyEvolutionNativeWave65Error(
            "packaged wave-65 ticket is not a sorted legal ticket"
        )
    return cast(Ticket, tuple(integers))


def _source_artifact_identity(value: object) -> tuple[str, str, int, str]:
    if not isinstance(value, dict):
        raise LegacyEvolutionNativeWave65Error(
            "packaged wave-65 source artifact is invalid"
        )
    row = cast(dict[str, object], value)
    identity = (
        row.get("path"),
        row.get("blob_id"),
        row.get("byte_size"),
        row.get("sha256"),
    )
    if (
        type(identity[0]) is not str
        or type(identity[1]) is not str
        or type(identity[2]) is not int
        or type(identity[3]) is not str
    ):
        raise LegacyEvolutionNativeWave65Error(
            "packaged wave-65 source artifact identity changed"
        )
    return cast(tuple[str, str, int, str], identity)


@lru_cache(maxsize=1)
def _load_ledger() -> _Ledger:
    raw = (
        files("lottolab.strategies.data")
        .joinpath(LEDGER_RESOURCE_NAME)
        .read_bytes()
    )
    if hashlib.sha256(raw).hexdigest() != LEDGER_FILE_SHA256:
        raise LegacyEvolutionNativeWave65Error(
            "packaged wave-65 ledger file SHA changed"
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LegacyEvolutionNativeWave65Error(
            "packaged wave-65 ledger is invalid JSON"
        ) from exc
    if not isinstance(parsed, dict):
        raise LegacyEvolutionNativeWave65Error(
            "packaged wave-65 ledger must be an object"
        )
    document = cast(dict[str, Any], parsed)
    reduced = {
        key: value
        for key, value in document.items()
        if key != "ledger_content_sha256"
    }
    source_artifacts_raw = cast(
        list[object],
        document.get("source_artifacts", []),
    )
    if (
        document.get("ledger_schema_version") != LEDGER_SCHEMA_VERSION
        or document.get("ledger_content_sha256") != LEDGER_CONTENT_SHA256
        or hashlib.sha256(_canonical_bytes(reduced)).hexdigest()
        != LEDGER_CONTENT_SHA256
        or document.get("dataset_sha256") != PINNED_DATASET_SHA256
        or document.get("frozen_source_commit") != FROZEN_SOURCE_COMMIT
        or document.get("legacy_method_id") != METHOD_ID
        or document.get("causal_protocol") != CAUSAL_PROTOCOL
        or document.get("acceleration_protocol") != ACCELERATION_PROTOCOL
        or document.get("source_reference_runtime")
        != SOURCE_REFERENCE_RUNTIME
        or document.get("first_executable_target_index")
        != FIRST_EXECUTABLE_TARGET_INDEX
        or document.get("driver_generations") != DRIVER_GENERATIONS
        or document.get("driver_population_size")
        != DRIVER_POPULATION_SIZE
        or document.get("driver_n_test") != DRIVER_N_TEST
        or document.get("engine_seed") != ENGINE_SEED
        or tuple(
            _source_artifact_identity(value)
            for value in source_artifacts_raw
        )
        != EXPECTED_SOURCE_ARTIFACTS
        or document.get("ticket_sequence_sha256")
        != TICKET_SEQUENCE_SHA256
        or document.get("leaderboard_sequence_sha256")
        != LEADERBOARD_SEQUENCE_SHA256
        or document.get("status_sequence_sha256")
        != STATUS_SEQUENCE_SHA256
        or document.get("context_sequence_sha256")
        != CONTEXT_SEQUENCE_SHA256
        or document.get("native_ticket_position_count") != 12959
        or document.get("native_ticket_count_distribution")
        != EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTION
        or document.get("native_duplicate_ticket_count_distribution")
        != EXPECTED_NATIVE_DUPLICATE_DISTRIBUTION
    ):
        raise LegacyEvolutionNativeWave65Error(
            "packaged wave-65 ledger identity changed"
        )
    targets_raw = cast(
        list[object],
        document.get("target_draw_numbers", []),
    )
    contexts_raw = cast(
        list[object],
        document.get("context_numbers_sha256_by_target", []),
    )
    counts_raw = cast(
        list[object],
        document.get("history_input_draw_count", []),
    )
    tickets_raw = cast(
        list[object],
        document.get("native_tickets_by_target", []),
    )
    leaderboard_raw = cast(
        list[object],
        document.get("leaderboard_by_target", []),
    )
    populations_raw = cast(
        list[object],
        document.get("generation_population_by_target", []),
    )
    totals_raw = cast(
        list[object],
        document.get("total_strategies_tested_by_target", []),
    )
    patterns_raw = cast(
        list[object],
        document.get("pattern_exists_by_target", []),
    )
    statuses_raw = cast(
        list[object],
        document.get("execution_status_by_target", []),
    )
    reasons_raw = cast(
        list[object],
        document.get("closed_reason_by_target", []),
    )
    arrays = (
        targets_raw,
        contexts_raw,
        counts_raw,
        tickets_raw,
        leaderboard_raw,
        populations_raw,
        totals_raw,
        patterns_raw,
        statuses_raw,
        reasons_raw,
    )
    if any(len(values) != 2149 for values in arrays):
        raise LegacyEvolutionNativeWave65Error(
            "packaged wave-65 coverage changed"
        )
    if (
        targets_raw[0] != "96000001"
        or targets_raw[-1] != "115000073"
        or not all(type(value) is str for value in targets_raw)
        or len(set(cast(list[str], targets_raw))) != 2149
        or not all(
            isinstance(value, str) and len(value) == 64
            for value in contexts_raw
        )
        or counts_raw != list(range(2149))
        or hashlib.sha256(_canonical_bytes(contexts_raw)).hexdigest()
        != CONTEXT_SEQUENCE_SHA256
        or hashlib.sha256(_canonical_bytes(statuses_raw)).hexdigest()
        != STATUS_SEQUENCE_SHA256
        or hashlib.sha256(_canonical_bytes(tickets_raw)).hexdigest()
        != TICKET_SEQUENCE_SHA256
        or hashlib.sha256(_canonical_bytes(leaderboard_raw)).hexdigest()
        != LEADERBOARD_SEQUENCE_SHA256
    ):
        raise LegacyEvolutionNativeWave65Error(
            "packaged wave-65 target sequence changed"
        )
    portfolios: list[tuple[Ticket, ...] | None] = []
    leaderboards: list[tuple[dict[str, object], ...] | None] = []
    populations: list[tuple[int, ...] | None] = []
    totals: list[int | None] = []
    patterns: list[bool | None] = []
    statuses: list[str] = []
    reasons: list[str | None] = []
    ticket_counts: Counter[int] = Counter()
    duplicate_counts: Counter[int] = Counter()
    for index in range(2149):
        if index < FIRST_EXECUTABLE_TARGET_INDEX:
            if (
                statuses_raw[index] != "CLOSED_INSUFFICIENT_HISTORY"
                or reasons_raw[index] != CLOSED_REASON
                or tickets_raw[index] is not None
                or leaderboard_raw[index] is not None
                or populations_raw[index] is not None
                or totals_raw[index] is not None
                or patterns_raw[index] is not None
            ):
                raise LegacyEvolutionNativeWave65Error(
                    "packaged wave-65 closed boundary changed"
                )
            portfolios.append(None)
            leaderboards.append(None)
            populations.append(None)
            totals.append(None)
            patterns.append(None)
            statuses.append("CLOSED_INSUFFICIENT_HISTORY")
            reasons.append(CLOSED_REASON)
            continue
        portfolio_value = tickets_raw[index]
        leaderboard_value = leaderboard_raw[index]
        population_value = populations_raw[index]
        total_value = totals_raw[index]
        pattern_value = patterns_raw[index]
        if (
            statuses_raw[index] != "OK"
            or reasons_raw[index] is not None
            or not isinstance(portfolio_value, list)
            or not isinstance(leaderboard_value, list)
            or not 1 <= len(cast(list[object], portfolio_value)) <= 10
            or len(cast(list[object], leaderboard_value))
            != len(cast(list[object], portfolio_value))
            or not isinstance(population_value, list)
            or len(cast(list[object], population_value))
            != DRIVER_GENERATIONS
            or any(
                type(value) is not int or value <= 0
                for value in cast(list[object], population_value)
            )
            or type(total_value) is not int
            or total_value <= 0
            or type(pattern_value) is not bool
        ):
            raise LegacyEvolutionNativeWave65Error(
                "packaged wave-65 executable row changed"
            )
        portfolio = tuple(
            _ticket(ticket)
            for ticket in cast(list[object], portfolio_value)
        )
        leaderboard_items: list[dict[str, object]] = []
        for position, candidate in enumerate(
            cast(list[object], leaderboard_value)
        ):
            if not isinstance(candidate, dict):
                raise LegacyEvolutionNativeWave65Error(
                    "packaged wave-65 leaderboard row changed"
                )
            item = cast(dict[str, object], candidate)
            if _ticket(item.get("numbers")) != portfolio[position]:
                raise LegacyEvolutionNativeWave65Error(
                    "packaged wave-65 leaderboard order changed"
                )
            leaderboard_items.append(dict(item))
        duplicate_count = len(portfolio) - len(set(portfolio))
        ticket_counts[len(portfolio)] += 1
        duplicate_counts[duplicate_count] += 1
        portfolios.append(portfolio)
        leaderboards.append(tuple(leaderboard_items))
        populations.append(
            tuple(cast(list[int], population_value))
        )
        totals.append(total_value)
        patterns.append(pattern_value)
        statuses.append("OK")
        reasons.append(None)
    if (
        {str(key): value for key, value in sorted(ticket_counts.items())}
        != EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTION
        or {
            str(key): value
            for key, value in sorted(duplicate_counts.items())
        }
        != EXPECTED_NATIVE_DUPLICATE_DISTRIBUTION
        or sum(
            len(portfolio)
            for portfolio in portfolios
            if portfolio is not None
        )
        != 12959
    ):
        raise LegacyEvolutionNativeWave65Error(
            "packaged wave-65 ticket distribution changed"
        )
    targets = cast(tuple[str, ...], tuple(targets_raw))
    return _Ledger(
        targets=targets,
        target_index=MappingProxyType(
            {
                target: index
                for index, target in enumerate(targets)
            }
        ),
        context_sha256=cast(tuple[str, ...], tuple(contexts_raw)),
        history_input_draw_count=cast(
            tuple[int, ...],
            tuple(counts_raw),
        ),
        tickets=tuple(portfolios),
        leaderboard=tuple(leaderboards),
        generation_population=tuple(populations),
        total_strategies_tested=tuple(totals),
        pattern_exists=tuple(patterns),
        status=tuple(statuses),
        closed_reason=tuple(reasons),
    )


def load_legacy_evolution_native_wave65_ledger_for_verification() -> _Ledger:
    """Expose the immutable checksummed ledger to verification code."""

    return _load_ledger()


def _context_sha256(
    history: tuple[LegacyHistoryDraw, ...],
) -> str:
    return hashlib.sha256(
        json.dumps(
            [list(draw.numbers) for draw in history],
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def generate_legacy_evolution_native_wave65_portfolio(
    request: LegacyEvolutionNativeWave65Request,
) -> LegacyEvolutionNativeWave65Result:
    """Replay one causal frozen evolution-engine native leaderboard."""

    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.target_draw_date) is not date
        or request.dataset_sha256 != PINNED_DATASET_SHA256
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
    ):
        raise LegacyEvolutionNativeWave65Error(
            "invalid wave-65 request identity"
        )
    ledger = _load_ledger()
    target_index = ledger.target_index.get(request.target_draw_number)
    if target_index is None:
        raise LegacyEvolutionNativeWave65SourceError(
            "TARGET_OUTSIDE_FROZEN_WAVE65_TICKET_LEDGER"
        )
    context_sha256 = _context_sha256(request.history)
    if context_sha256 != ledger.context_sha256[target_index]:
        raise LegacyEvolutionNativeWave65SourceError(
            "FROZEN_WAVE65_FULL_PREFIX_CONTEXT_MISMATCH"
        )
    tickets = ledger.tickets[target_index]
    if tickets is None:
        raise LegacyEvolutionNativeWave65SourceError(
            ledger.closed_reason[target_index]
            or "FROZEN_WAVE65_CLOSED_WITHOUT_REASON"
        )
    leaderboard = ledger.leaderboard[target_index]
    population = ledger.generation_population[target_index]
    total_tested = ledger.total_strategies_tested[target_index]
    pattern_exists = ledger.pattern_exists[target_index]
    if (
        leaderboard is None
        or population is None
        or total_tested is None
        or pattern_exists is None
        or len(request.history) <= 500
        or len(tickets) != len(leaderboard)
    ):
        raise LegacyEvolutionNativeWave65Error(
            "executable wave-65 row lacks causal evolution state"
        )
    seed_material = (
        "engine_seed=42;driver_generations=8;"
        "driver_population_size=50;driver_n_test=1500"
    )
    return LegacyEvolutionNativeWave65Result(
        tickets=tickets,
        metadata=LegacyEvolutionNativeWave65Metadata(
            protocol=SOURCE_NATIVE_WAVE65_PROTOCOL,
            causal_protocol=CAUSAL_PROTOCOL,
            legacy_method_id=METHOD_ID,
            source_sha256=SOURCE_SHA256,
            target_draw_number=request.target_draw_number,
            target_draw_date=request.target_draw_date.isoformat(),
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=hashlib.sha256(
                seed_material.encode("utf-8")
            ).hexdigest(),
            determinism_protocol=DETERMINISM_PROTOCOL,
            randomness_used=True,
            source_random_state_explicit=True,
            repeatability_parity_passed=True,
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="OLDEST_FIRST",
            source_history_input_draw_count=(
                ledger.history_input_draw_count[target_index]
            ),
            context_draw_count=len(request.history),
            context_numbers_sha256=context_sha256,
            source_candidate_k_values=(),
            candidate_k=None,
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=NATIVE_TICKET_SEMANTICS,
            native_ticket_order=NATIVE_TICKET_ORDER,
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            combination_count=None,
            driver_generations=DRIVER_GENERATIONS,
            driver_population_size=DRIVER_POPULATION_SIZE,
            driver_n_test=DRIVER_N_TEST,
            engine_seed=ENGINE_SEED,
            generation_population=population,
            total_strategies_tested=total_tested,
            pattern_exists=pattern_exists,
            leaderboard=leaderboard,
            causal_eligibility_rule=CAUSAL_ELIGIBILITY_RULE,
            source_reference_runtime=SOURCE_REFERENCE_RUNTIME,
            acceleration_protocol=ACCELERATION_PROTOCOL,
            ledger_schema_version=LEDGER_SCHEMA_VERSION,
            ledger_file_sha256=LEDGER_FILE_SHA256,
            ledger_content_sha256=LEDGER_CONTENT_SHA256,
            ledger_target_index=target_index,
        ),
    )


__all__ = [
    "ACCELERATION_PROTOCOL",
    "CAUSAL_ELIGIBILITY_RULE",
    "CAUSAL_PROTOCOL",
    "CLOSED_REASON",
    "CONTEXT_POLICY",
    "DEFAULT_SOURCE_NATIVE_WAVE65_USER_SEED",
    "DETERMINISM_PROTOCOL",
    "DRIVER_GENERATIONS",
    "DRIVER_N_TEST",
    "DRIVER_POPULATION_SIZE",
    "ENGINE_SEED",
    "EXPECTED_NATIVE_DUPLICATE_DISTRIBUTION",
    "EXPECTED_NATIVE_TICKET_COUNT_DISTRIBUTION",
    "FIRST_EXECUTABLE_TARGET_INDEX",
    "FROZEN_SOURCE_COMMIT",
    "LEADERBOARD_SEQUENCE_SHA256",
    "LEDGER_CONTENT_SHA256",
    "LEDGER_FILE_SHA256",
    "LEDGER_RESOURCE_NAME",
    "LEDGER_SCHEMA_VERSION",
    "METHOD_ID",
    "NATIVE_TICKET_ORDER",
    "NATIVE_TICKET_SEMANTICS",
    "PINNED_DATASET_SHA256",
    "SOURCE_NATIVE_WAVE65_PROTOCOL",
    "SOURCE_REFERENCE_RUNTIME",
    "SOURCE_SHA256",
    "TICKET_SEQUENCE_SHA256",
    "LegacyEvolutionNativeWave65Error",
    "LegacyEvolutionNativeWave65Metadata",
    "LegacyEvolutionNativeWave65Request",
    "LegacyEvolutionNativeWave65Result",
    "LegacyEvolutionNativeWave65SourceError",
    "generate_legacy_evolution_native_wave65_portfolio",
    "load_legacy_evolution_native_wave65_ledger_for_verification",
]
