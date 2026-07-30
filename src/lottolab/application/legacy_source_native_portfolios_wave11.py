"""Faithful ports of the eleventh frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
import random
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE11_PROTOCOL = "legacy_source_native_wave11/v1"
DEFAULT_SOURCE_NATIVE_WAVE11_USER_SEED = (
    "biglotto-full-universe-source-native-wave11-v1"
)
EXHAUSTIVE_NBET_METHOD_ID = "tools/exhaustive_nbet_benchmark.py"
MUST_HIT_METHOD_ID = "tools/backtest_must_hit.py"
SUPPORTED_SOURCE_NATIVE_WAVE11_METHODS = (
    EXHAUSTIVE_NBET_METHOD_ID,
    MUST_HIT_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE11_METHOD: Final = {
    EXHAUSTIVE_NBET_METHOD_ID: (
        "7e19a8676bfdef1af9381389103a900f9ee952217efb5597b39f8712482a579b"
    ),
    MUST_HIT_METHOD_ID: (
        "909c91fd2fd0b2ce100f645eb993ea6d25fc05238fef9b8a522df0816a28c6f0"
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE11_METHOD: Final = {
    EXHAUSTIVE_NBET_METHOD_ID: 500,
    MUST_HIT_METHOD_ID: 50,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE11_METHOD: Final = {
    EXHAUSTIVE_NBET_METHOD_ID: (
        "26_BIG_LOTTO_SOURCE_STRATEGY_CONFIGURATIONS_FLATTENED_TO_"
        "65_POSITIONAL_TICKETS_WITH_REPEATS"
    ),
    MUST_HIT_METHOD_ID: (
        "TOP6_CONFIGURATION_AS_ONE_LEGAL_TICKET_WITH_TOP10_AND_TOP15_"
        "RETAINED_AS_CANDIDATE_POOLS"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE11_METHOD: Final = {
    EXHAUSTIVE_NBET_METHOD_ID: (
        "random.seed(42)_RESET_INSIDE_EACH_SUM_OPTIMAL_CALL"
    ),
    MUST_HIT_METHOD_ID: "NONE_DETERMINISTIC",
}
CANDIDATE_K_BY_SOURCE_NATIVE_WAVE11_METHOD: Final = {
    method_id: None
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE11_METHODS
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE11_METHOD: Final = {
    EXHAUSTIVE_NBET_METHOD_ID: 26,
    MUST_HIT_METHOD_ID: 3,
}
_EXHAUSTIVE_METHOD_NAMES = (
    "method_frequency_hot",
    "method_frequency_cold",
    "method_gap_pressure",
    "method_markov_transition",
    "method_zone_balance",
    "method_odd_even_balance",
    "method_sum_optimal",
    "method_clustering_centroid",
    "method_entropy_max",
    "method_anti_repeat",
    "method_tail_pattern",
    "method_hybrid_hot_cold",
)
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE11_METHOD: Final = {
    EXHAUSTIVE_NBET_METHOD_ID: tuple(
        [
            f"BIG_LOTTO_2BET:{name}"
            for name in _EXHAUSTIVE_METHOD_NAMES
        ]
        + ["BIG_LOTTO_2BET:DIVERSE_ENSEMBLE"]
        + [
            f"BIG_LOTTO_3BET:{name}"
            for name in _EXHAUSTIVE_METHOD_NAMES
        ]
        + ["BIG_LOTTO_3BET:DIVERSE_ENSEMBLE"]
    ),
    MUST_HIT_METHOD_ID: (
        "predict_must_hit:top_n=6",
        "predict_must_hit:top_n=10",
        "predict_must_hit:top_n=15",
    ),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE11_METHOD: Final = {
    EXHAUSTIVE_NBET_METHOD_ID: "RECENT_FIRST",
    MUST_HIT_METHOD_ID: "OLDEST_FIRST",
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6


class LegacySourceNativeWave11Error(ValueError):
    """A request cannot satisfy the eleventh source-native contract."""


class LegacySourceNativeWave11SourceError(
    LegacySourceNativeWave11Error
):
    """A frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave11Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE11_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave11Metadata:
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
    source_candidate_number_pools: tuple[tuple[int, ...], ...]
    excluded_non_strategy_source_members: tuple[str, ...]
    source_runtime_parameters: tuple[str, ...]
    candidate_k: None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave11Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave11Metadata


@dataclass(frozen=True, slots=True)
class _RawPortfolio:
    tickets: tuple[list[int], ...]
    source_candidate_ticket_counts: tuple[int, ...]
    source_candidate_k_values: tuple[int, ...] = ()
    source_candidate_number_pools: tuple[tuple[int, ...], ...] = ()
    excluded_non_strategy_source_members: tuple[str, ...] = ()
    source_runtime_parameters: tuple[str, ...] = ()


History = tuple[tuple[int, ...], ...]
Selector = Callable[[History, int], list[int]]


def _validate_request(request: LegacySourceNativeWave11Request) -> None:
    if (
        request.legacy_method_id
        not in SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE11_METHOD
    ):
        raise LegacySourceNativeWave11Error(
            "legacy method is outside the eleventh source-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacySourceNativeWave11Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacySourceNativeWave11Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacySourceNativeWave11Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacySourceNativeWave11Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(draw.numbers)


def _seed(
    request: LegacySourceNativeWave11Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE11_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE11_METHOD[
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
        raise LegacySourceNativeWave11SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _frequency_hot(history: History, _max_num: int) -> list[int]:
    counter: Counter[int] = Counter()
    for draw in history[:50]:
        counter.update(draw)
    return [number for number, _count in counter.most_common(6)]


def _frequency_cold(history: History, max_num: int) -> list[int]:
    counter: Counter[int] = Counter()
    for draw in history[:100]:
        counter.update(draw)
    all_numbers = set(range(1, max_num + 1))
    for number in all_numbers:
        if number not in counter:
            counter[number] = 0
    return [
        number for number, _count in counter.most_common()[-6:]
    ]


def _gap_pressure(history: History, max_num: int) -> list[int]:
    gaps = {number: 0 for number in range(1, max_num + 1)}
    for number in gaps:
        for index, draw in enumerate(history):
            if number in draw:
                gaps[number] = index
                break
        else:
            gaps[number] = len(history)
    sorted_gaps = sorted(
        gaps.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    return [number for number, _gap in sorted_gaps[:6]]


def _markov_transition(history: History, max_num: int) -> list[int]:
    if len(history) < 2:
        return list(range(1, 7))
    last_draw = set(history[0])
    transitions: Counter[tuple[int, int]] = Counter()
    for index in range(1, len(history) - 1):
        previous = set(history[index + 1])
        current = set(history[index])
        for previous_number in previous:
            for current_number in current:
                transitions[(previous_number, current_number)] += 1
    scores: Counter[int] = Counter()
    for number in last_draw:
        for target in range(1, max_num + 1):
            scores[target] += transitions.get((number, target), 0)
    return [number for number, _count in scores.most_common(6)]


def _zone_balance(history: History, max_num: int) -> list[int]:
    zone_size = max_num // 3
    zones = (
        range(1, zone_size + 1),
        range(zone_size + 1, 2 * zone_size + 1),
        range(2 * zone_size + 1, max_num + 1),
    )
    counter: Counter[int] = Counter()
    for draw in history[:50]:
        counter.update(draw)
    result: list[int] = []
    for zone in zones:
        zone_scores = [
            (number, counter.get(number, 0)) for number in zone
        ]
        zone_scores.sort(key=lambda item: item[1], reverse=True)
        result.extend(number for number, _count in zone_scores[:2])
    return sorted(result[:6])


def _odd_even_balance(history: History, max_num: int) -> list[int]:
    counter: Counter[int] = Counter()
    for draw in history[:50]:
        counter.update(draw)
    odds = [
        (number, counter.get(number, 0))
        for number in range(1, max_num + 1)
        if number % 2 == 1
    ]
    evens = [
        (number, counter.get(number, 0))
        for number in range(1, max_num + 1)
        if number % 2 == 0
    ]
    odds.sort(key=lambda item: item[1], reverse=True)
    evens.sort(key=lambda item: item[1], reverse=True)
    return sorted(
        [odds[index][0] for index in range(3)]
        + [evens[index][0] for index in range(3)]
    )


def _sum_optimal(history: History, max_num: int) -> list[int]:
    sums = [sum(draw) for draw in history[:200]]
    average_sum = sum(sums) / len(sums)
    rng = random.Random(42)
    all_numbers = list(range(1, max_num + 1))
    candidates = [
        rng.sample(all_numbers, 6) for _index in range(1000)
    ]
    best: list[int] | None = None
    best_difference = float("inf")
    for candidate in candidates:
        difference = abs(sum(candidate) - average_sum)
        if difference < best_difference:
            best_difference = difference
            best = candidate
    if best is None:
        raise LegacySourceNativeWave11SourceError(
            "FROZEN_SOURCE_NO_SUM_OPTIMAL_CANDIDATE"
        )
    return sorted(best)


def _clustering_centroid(history: History, max_num: int) -> list[int]:
    recent = history[:100]
    indexed = [
        (
            number,
            sum(1 for draw in recent if number in draw) / len(recent),
        )
        for number in range(1, max_num + 1)
    ]
    indexed.sort(key=lambda item: item[1], reverse=True)
    return [number for number, _score in indexed[:6]]


def _entropy_max(history: History, max_num: int) -> list[int]:
    cooccur: Counter[tuple[int, int]] = Counter()
    for draw in history[:100]:
        for pair in combinations(sorted(draw), 2):
            cooccur[pair] += 1
    scores = {number: 0 for number in range(1, max_num + 1)}
    for (left, right), count in cooccur.items():
        scores[left] += count
        scores[right] += count
    sorted_scores = sorted(
        scores.items(),
        key=lambda item: item[1],
    )
    return [number for number, _score in sorted_scores[:6]]


def _anti_repeat(history: History, max_num: int) -> list[int]:
    if not history:
        return list(range(1, 7))
    last = set(history[0])
    candidates = [
        number
        for number in range(1, max_num + 1)
        if number not in last
    ]
    counter: Counter[int] = Counter()
    for draw in history[:50]:
        counter.update(draw)
    candidate_scores = [
        (number, counter.get(number, 0)) for number in candidates
    ]
    candidate_scores.sort(
        key=lambda item: item[1],
        reverse=True,
    )
    return [number for number, _score in candidate_scores[:6]]


def _tail_pattern(history: History, max_num: int) -> list[int]:
    tail_counter: Counter[int] = Counter()
    for draw in history[:50]:
        for number in draw:
            tail_counter[number % 10] += 1
    best_tails = [
        tail for tail, _count in tail_counter.most_common(6)
    ]
    result: list[int] = []
    for tail in best_tails:
        for number in range(
            tail if tail > 0 else 10,
            max_num + 1,
            10,
        ):
            if number not in result:
                result.append(number)
                break
        if len(result) >= 6:
            break
    while len(result) < 6:
        for number in range(1, max_num + 1):
            if number not in result:
                result.append(number)
                break
    return sorted(result[:6])


def _hybrid_hot_cold(history: History, max_num: int) -> list[int]:
    hot = _frequency_hot(history, max_num)[:3]
    cold = _frequency_cold(history, max_num)[:3]
    return sorted(list(set(hot + cold))[:6])


_EXHAUSTIVE_METHODS: tuple[Selector, ...] = (
    _frequency_hot,
    _frequency_cold,
    _gap_pressure,
    _markov_transition,
    _zone_balance,
    _odd_even_balance,
    _sum_optimal,
    _clustering_centroid,
    _entropy_max,
    _anti_repeat,
    _tail_pattern,
    _hybrid_hot_cold,
)


def _exhaustive_nbet(history_oldest_first: History) -> _RawPortfolio:
    history = tuple(reversed(history_oldest_first))
    configurations: list[list[list[int]]] = []
    for number_of_bets in (2, 3):
        for method in _EXHAUSTIVE_METHODS:
            configurations.append(
                [
                    method(history, _MAX_NUMBER)
                    for _index in range(number_of_bets)
                ]
            )
        configurations.append(
            [
                _EXHAUSTIVE_METHODS[index](history, _MAX_NUMBER)
                for index in range(number_of_bets)
            ]
        )
    return _RawPortfolio(
        tickets=tuple(
            ticket
            for configuration in configurations
            for ticket in configuration
        ),
        source_candidate_ticket_counts=tuple(
            len(configuration) for configuration in configurations
        ),
        excluded_non_strategy_source_members=(
            "BIG_LOTTO_2BET:RANDOM_BASELINE",
            "BIG_LOTTO_3BET:RANDOM_BASELINE",
        ),
        source_runtime_parameters=(
            "source_periods=500",
            "source_context_history_minimum=500",
            "max_num=49",
        ),
    )


def _must_hit(history: History) -> _RawPortfolio:
    frequency: Counter[int] = Counter(
        number for draw in history[-50:] for number in draw
    )
    pools = tuple(
        tuple(
            number
            for number, _count in frequency.most_common(top_n)
        )
        for top_n in (6, 10, 15)
    )
    return _RawPortfolio(
        tickets=(list(pools[0]),),
        source_candidate_ticket_counts=(1, 0, 0),
        source_candidate_k_values=(6, 10, 15),
        source_candidate_number_pools=pools,
        source_runtime_parameters=(
            "source_run_top_n=6,10,15",
            "frequency_window=50",
        ),
    )


def _raw_portfolio(
    request: LegacySourceNativeWave11Request,
) -> _RawPortfolio:
    history = tuple(draw.numbers for draw in request.history)
    if request.legacy_method_id == EXHAUSTIVE_NBET_METHOD_ID:
        return _exhaustive_nbet(history)
    return _must_hit(history)


def generate_legacy_source_native_wave11_portfolio(
    request: LegacySourceNativeWave11Request,
) -> LegacySourceNativeWave11Result:
    """Generate source-ordered native tickets from strictly prior history."""

    _validate_request(request)
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE11_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave11Error(
            f"method requires at least {minimum} history draws"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    raw = _raw_portfolio(request)
    if not raw.tickets:
        raise LegacySourceNativeWave11SourceError(
            "FROZEN_SOURCE_NO_NATIVE_TICKETS"
        )
    tickets = tuple(_ticket(ticket) for ticket in raw.tickets)
    random_protocol = RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE11_METHOD[
        request.legacy_method_id
    ]
    return LegacySourceNativeWave11Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave11Metadata(
            protocol=SOURCE_NATIVE_WAVE11_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE11_METHOD[
                    request.legacy_method_id
                ]
            ),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol=random_protocol,
            randomness_used=random_protocol != "NONE_DETERMINISTIC",
            randomness_reproduction=(
                "SOURCE_DETERMINISTIC"
                if random_protocol == "NONE_DETERMINISTIC"
                else "FROZEN_SOURCE_LOCAL_SEED_EXACT"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order=(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE11_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE11_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_order=(
                "FROZEN_SOURCE_CONFIGURATION_AND_BET_LOOP_ORDER"
            ),
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            source_combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE11_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_candidate_ticket_counts=(
                raw.source_candidate_ticket_counts
            ),
            source_candidate_k_values=raw.source_candidate_k_values,
            source_candidate_number_pools=(
                raw.source_candidate_number_pools
            ),
            excluded_non_strategy_source_members=(
                raw.excluded_non_strategy_source_members
            ),
            source_runtime_parameters=raw.source_runtime_parameters,
            candidate_k=None,
            combination_count=None,
        ),
    )


__all__ = [
    "CANDIDATE_K_BY_SOURCE_NATIVE_WAVE11_METHOD",
    "DEFAULT_SOURCE_NATIVE_WAVE11_USER_SEED",
    "EXHAUSTIVE_NBET_METHOD_ID",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE11_METHOD",
    "MUST_HIT_METHOD_ID",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE11_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE11_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE11_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE11_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE11_METHOD",
    "SOURCE_NATIVE_WAVE11_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE11_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE11_METHODS",
    "LegacySourceNativeWave11Error",
    "LegacySourceNativeWave11Metadata",
    "LegacySourceNativeWave11Request",
    "LegacySourceNativeWave11Result",
    "LegacySourceNativeWave11SourceError",
    "generate_legacy_source_native_wave11_portfolio",
]
