"""Faithful ports of the fourteenth frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE14_PROTOCOL = "legacy_source_native_wave14/v1"
DEFAULT_SOURCE_NATIVE_WAVE14_USER_SEED = (
    "biglotto-full-universe-source-native-wave14-v1"
)
GRAPH_PREDICTOR_METHOD_ID = "ai_lab/scripts/graph_predictor.py"
HIGH_PRIZE_TREND_METHOD_ID = (
    "ai_lab/scripts/high_prize_trend_optimizer.py"
)
SUPPORTED_SOURCE_NATIVE_WAVE14_METHODS = (
    GRAPH_PREDICTOR_METHOD_ID,
    HIGH_PRIZE_TREND_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD: Final = {
    GRAPH_PREDICTOR_METHOD_ID: (
        "cd70713a5709065ce9841b47591684ba70586a0be0a52a46dbfc3237a4956be9"
    ),
    HIGH_PRIZE_TREND_METHOD_ID: (
        "0fc72409150e64bdfb6f3a3714c60635c13e801b7b576c01be6c671b20e5bfbc"
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE14_METHOD: Final = {
    GRAPH_PREDICTOR_METHOD_ID: 1,
    HIGH_PRIZE_TREND_METHOD_ID: 100,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE14_METHOD: Final = {
    GRAPH_PREDICTOR_METHOD_ID: (
        "ONE_PAGERANK_TOP15_GREEDY_CLIQUE_TICKET"
    ),
    HIGH_PRIZE_TREND_METHOD_ID: (
        "SEVEN_BIG_LOTTO_LAMBDA_CONFIGURATIONS_FLATTENED_IN_SOURCE_ORDER"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE14_METHOD: Final = {
    method_id: "NONE_DETERMINISTIC"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE14_METHODS
}
CANDIDATE_K_BY_SOURCE_NATIVE_WAVE14_METHOD: Final = {
    GRAPH_PREDICTOR_METHOD_ID: 15,
    HIGH_PRIZE_TREND_METHOD_ID: None,
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE14_METHOD: Final = {
    GRAPH_PREDICTOR_METHOD_ID: None,
    HIGH_PRIZE_TREND_METHOD_ID: 7,
}
_TREND_LAMBDAS = (0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.15)
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE14_METHOD: Final = {
    GRAPH_PREDICTOR_METHOD_ID: (),
    HIGH_PRIZE_TREND_METHOD_ID: tuple(
        f"BIG_LOTTO:lambda={value:.2f}" for value in _TREND_LAMBDAS
    ),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE14_METHOD: Final = {
    method_id: "OLDEST_FIRST"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE14_METHODS
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6


class LegacySourceNativeWave14Error(ValueError):
    """A request cannot satisfy the fourteenth source-native contract."""


class LegacySourceNativeWave14SourceError(
    LegacySourceNativeWave14Error
):
    """A frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave14Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE14_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave14Metadata:
    protocol: str
    legacy_method_id: str
    source_sha256: str
    target_draw_number: str
    replicate_id: int
    user_seed: str | int
    seed_material: str
    seed_digest: str
    seed_integer: int
    random_protocol: str
    randomness_used: bool
    randomness_reproduction: str
    history_draw_count: int
    history_first_draw_number: str
    history_cutoff_draw_number: str
    source_history_order: str
    native_ticket_count: int
    native_ticket_count_semantics: str
    native_ticket_order: str
    native_duplicate_ticket_count: int
    source_combination_members: tuple[str, ...]
    source_candidate_ticket_counts: tuple[int, ...]
    source_candidate_k_values: tuple[int, ...]
    excluded_non_strategy_source_members: tuple[str, ...]
    source_runtime_parameters: tuple[str, ...]
    candidate_k: None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave14Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave14Metadata


@dataclass(frozen=True, slots=True)
class _RawPortfolio:
    tickets: tuple[list[int], ...]
    source_candidate_ticket_counts: tuple[int, ...]
    source_candidate_k_values: tuple[int, ...] = ()
    excluded_non_strategy_source_members: tuple[str, ...] = ()
    source_runtime_parameters: tuple[str, ...] = ()


History = tuple[tuple[int, ...], ...]


def _validate_request(request: LegacySourceNativeWave14Request) -> None:
    if (
        request.legacy_method_id
        not in SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD
    ):
        raise LegacySourceNativeWave14Error(
            "legacy method is outside the fourteenth source-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacySourceNativeWave14Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacySourceNativeWave14Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacySourceNativeWave14Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacySourceNativeWave14Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(draw.numbers)


def _seed(
    request: LegacySourceNativeWave14Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE14_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _ticket(numbers: tuple[int, ...] | list[int]) -> Ticket:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(
            type(number) is not int
            or not _MIN_NUMBER <= number <= _MAX_NUMBER
            for number in values
        )
    ):
        raise LegacySourceNativeWave14SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _graph_predictor(history: History) -> _RawPortfolio:
    adjacency: defaultdict[int, defaultdict[int, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    for age, draw in enumerate(reversed(history)):
        weight = math.exp(-0.02 * age)
        for first, second in combinations(draw, 2):
            adjacency[first][second] += weight
            adjacency[second][first] += weight

    nodes = tuple(range(_MIN_NUMBER, _MAX_NUMBER + 1))
    rank = {number: 1.0 / _MAX_NUMBER for number in nodes}
    for _iteration in range(20):
        new_rank: dict[int, float] = {}
        for number in nodes:
            incoming = sum(
                adjacency[other].get(number, 0.0)
                * rank[other]
                / max(sum(adjacency[other].values()), 1)
                for other in nodes
                if adjacency[other].get(number, 0.0) > 0
            )
            new_rank[number] = (
                (1 - 0.85) / _MAX_NUMBER + 0.85 * incoming
            )
        rank = new_rank

    ranked = sorted(
        rank.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    candidates = [number for number, _score in ranked[:15]]
    selected: list[int] = []
    remaining = list(candidates)
    while len(selected) < _PICK_COUNT and remaining:
        best: int | None = None
        best_score = -1.0
        for candidate in remaining:
            score = (
                sum(
                    adjacency[candidate].get(chosen, 0.0)
                    for chosen in selected
                )
                + 0.1
            )
            if score > best_score:
                best_score = score
                best = candidate
        if best is not None:
            selected.append(best)
            remaining.remove(best)

    return _RawPortfolio(
        tickets=(sorted(selected),),
        source_candidate_ticket_counts=(1,),
        source_candidate_k_values=(15,),
        source_runtime_parameters=(
            "decay_lambda=0.02",
            "pagerank_damping=0.85",
            "pagerank_iterations=20",
            "candidate_k=15",
        ),
    )


def _trend_ticket(history: History, lambda_value: float) -> list[int]:
    weighted_frequency: defaultdict[int, float] = defaultdict(float)
    for age, draw in enumerate(reversed(history)):
        weight = math.exp(-lambda_value * age)
        for number in draw:
            weighted_frequency[number] += weight
    total = sum(weighted_frequency.values())
    probabilities = {
        number: weighted_frequency.get(number, 0.0) / total
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
    }
    ranked = sorted(
        probabilities.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    return sorted(
        number for number, _probability in ranked[:_PICK_COUNT]
    )


def _high_prize_trend(history: History) -> _RawPortfolio:
    tickets = tuple(
        _trend_ticket(history, lambda_value)
        for lambda_value in _TREND_LAMBDAS
    )
    return _RawPortfolio(
        tickets=tickets,
        source_candidate_ticket_counts=tuple(1 for _ in _TREND_LAMBDAS),
        excluded_non_strategy_source_members=(
            "TrendFocusedHighPrize2Bet:not_invoked_by_frozen___main__",
            "POWER_LOTTO:test_lambda_values_branch",
        ),
        source_runtime_parameters=tuple(
            f"BIG_LOTTO:lambda={value:.2f}"
            for value in _TREND_LAMBDAS
        ),
    )


def _raw_portfolio(
    method_id: str,
    history: History,
) -> _RawPortfolio:
    if method_id == GRAPH_PREDICTOR_METHOD_ID:
        return _graph_predictor(history)
    if method_id == HIGH_PRIZE_TREND_METHOD_ID:
        return _high_prize_trend(history)
    raise LegacySourceNativeWave14Error(
        "legacy method is outside the fourteenth source-native batch"
    )


def generate_legacy_source_native_wave14_portfolio(
    request: LegacySourceNativeWave14Request,
) -> LegacySourceNativeWave14Result:
    """Reproduce one frozen source-native portfolio without target outcomes."""

    _validate_request(request)
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE14_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave14SourceError(
            "AVAILABLE_HISTORY_BELOW_FROZEN_SOURCE_MINIMUM"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    history = tuple(draw.numbers for draw in request.history)
    raw = _raw_portfolio(request.legacy_method_id, history)
    tickets = tuple(_ticket(ticket) for ticket in raw.tickets)
    if not tickets:
        raise LegacySourceNativeWave14SourceError(
            "FROZEN_SOURCE_EMPTY_NATIVE_PORTFOLIO"
        )
    duplicate_count = len(tickets) - len(set(tickets))
    metadata = LegacySourceNativeWave14Metadata(
        protocol=SOURCE_NATIVE_WAVE14_PROTOCOL,
        legacy_method_id=request.legacy_method_id,
        source_sha256=(
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD[
                request.legacy_method_id
            ]
        ),
        target_draw_number=request.target_draw_number,
        replicate_id=request.replicate_id,
        user_seed=request.user_seed,
        seed_material=seed_material,
        seed_digest=seed_digest,
        seed_integer=seed_integer,
        random_protocol=(
            RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE14_METHOD[
                request.legacy_method_id
            ]
        ),
        randomness_used=False,
        randomness_reproduction="NONE_DETERMINISTIC",
        history_draw_count=len(request.history),
        history_first_draw_number=request.history[0].draw_number,
        history_cutoff_draw_number=request.history[-1].draw_number,
        source_history_order=(
            SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE14_METHOD[
                request.legacy_method_id
            ]
        ),
        native_ticket_count=len(tickets),
        native_ticket_count_semantics=(
            NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE14_METHOD[
                request.legacy_method_id
            ]
        ),
        native_ticket_order=(
            "FROZEN_SOURCE_CONFIGURATION_THEN_TICKET_ORDER"
        ),
        native_duplicate_ticket_count=duplicate_count,
        source_combination_members=(
            SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE14_METHOD[
                request.legacy_method_id
            ]
        ),
        source_candidate_ticket_counts=(
            raw.source_candidate_ticket_counts
        ),
        source_candidate_k_values=raw.source_candidate_k_values,
        excluded_non_strategy_source_members=(
            raw.excluded_non_strategy_source_members
        ),
        source_runtime_parameters=raw.source_runtime_parameters,
        candidate_k=None,
        combination_count=None,
    )
    return LegacySourceNativeWave14Result(
        tickets=tickets,
        metadata=metadata,
    )


__all__ = [
    "CANDIDATE_K_BY_SOURCE_NATIVE_WAVE14_METHOD",
    "DEFAULT_SOURCE_NATIVE_WAVE14_USER_SEED",
    "GRAPH_PREDICTOR_METHOD_ID",
    "HIGH_PRIZE_TREND_METHOD_ID",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE14_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE14_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE14_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE14_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE14_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE14_METHOD",
    "SOURCE_NATIVE_WAVE14_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE14_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE14_METHODS",
    "LegacySourceNativeWave14Error",
    "LegacySourceNativeWave14Metadata",
    "LegacySourceNativeWave14Request",
    "LegacySourceNativeWave14Result",
    "LegacySourceNativeWave14SourceError",
    "generate_legacy_source_native_wave14_portfolio",
]
