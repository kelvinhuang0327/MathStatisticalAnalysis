"""Faithful ports of the sixth frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
import random
from collections import Counter
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.legacy_history_native_portfolios_wave5 import (
    legacy_continuous_temperature,
    legacy_echo_detector,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE6_PROTOCOL = "legacy_source_native_wave6/v1"
DEFAULT_SOURCE_NATIVE_WAVE6_USER_SEED = (
    "biglotto-full-universe-source-native-wave6-v1"
)
ECHO_PHASE2_METHOD_ID = "tools/predict_biglotto_echo_phase2.py"
HOT_STOP_REBOUND_METHOD_ID = (
    "tools/backtest_biglotto_hot_stop_rebound.py"
)
COMPARE_RANDOM_METHOD_ID = "tools/compare_random_vs_smart.py"
SBP_RANDOM_METHOD_ID = "tools/sbp_baseline_check.py"
SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS = (
    ECHO_PHASE2_METHOD_ID,
    HOT_STOP_REBOUND_METHOD_ID,
    COMPARE_RANDOM_METHOD_ID,
    SBP_RANDOM_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE6_METHOD: Final = {
    ECHO_PHASE2_METHOD_ID: (
        "51c44b5c13d40b209a95501cc42e46d6fd3b92515f2a2d1c865b464ee5c546f5"
    ),
    HOT_STOP_REBOUND_METHOD_ID: (
        "1794a8c507aed174efe13310a3a3b7774158149931ce70101a2cfb729d54b2f5"
    ),
    COMPARE_RANDOM_METHOD_ID: (
        "ba5fdd5fd75d5fdd110e440b0611b79f9ca11daa4fa9fd59cfa60e298640ed5d"
    ),
    SBP_RANDOM_METHOD_ID: (
        "90e91add9209cb1e871f5ab9ad9948977a3e35ac0ab0ccf3c6c5e52af3e0c122"
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE6_METHOD: Final = {
    ECHO_PHASE2_METHOD_ID: 1,
    HOT_STOP_REBOUND_METHOD_ID: 200,
    COMPARE_RANDOM_METHOD_ID: 1,
    SBP_RANDOM_METHOD_ID: 1,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE6_METHOD: Final = {
    ECHO_PHASE2_METHOD_ID: (
        "PHASE2_2BET_THEN_PHASE2_3BET_SOURCE_ORDER_5_POSITIONAL_TICKETS"
    ),
    HOT_STOP_REBOUND_METHOD_ID: (
        "EIGHT_SOURCE_PARAMETER_GRID_CONFIGURATIONS_IN_DECLARATION_ORDER"
    ),
    COMPARE_RANDOM_METHOD_ID: (
        "GENERATE_RANDOM_5_BETS_SOURCE_CALL_ORDER"
    ),
    SBP_RANDOM_METHOD_ID: "RANDOM_BASELINE_3_BETS_SOURCE_CALL_ORDER",
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE6_METHOD: Final = {
    ECHO_PHASE2_METHOD_ID: "NONE_DETERMINISTIC",
    HOT_STOP_REBOUND_METHOD_ID: "NONE_DETERMINISTIC",
    COMPARE_RANDOM_METHOD_ID: (
        "random.Random(MT19937)_TARGET_STABLE_REPLACEMENT_"
        "FOR_UNPRESERVED_MODULE_GLOBAL_STATE"
    ),
    SBP_RANDOM_METHOD_ID: (
        "random.Random(MT19937)_TARGET_STABLE_REPLACEMENT_"
        "FOR_HORIZON_ORDER_DEPENDENT_GLOBAL_STREAM"
    ),
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE6_METHOD: Final = {
    ECHO_PHASE2_METHOD_ID: 2,
    HOT_STOP_REBOUND_METHOD_ID: 8,
    COMPARE_RANDOM_METHOD_ID: None,
    SBP_RANDOM_METHOD_ID: None,
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE6_METHOD: Final = {
    ECHO_PHASE2_METHOD_ID: (
        "phase2_echo_2bet:window=50,lookback=50",
        "phase2_echo_3bet:window=50,lookback=50",
    ),
    HOT_STOP_REBOUND_METHOD_ID: (
        "generate_hot_stop_bet:freq_threshold=12,gap_threshold=8",
        "generate_hot_stop_bet:freq_threshold=12,gap_threshold=10",
        "generate_hot_stop_bet:freq_threshold=15,gap_threshold=8",
        "generate_hot_stop_bet:freq_threshold=15,gap_threshold=10",
        "generate_hot_stop_bet:freq_threshold=15,gap_threshold=12",
        "generate_hot_stop_bet:freq_threshold=18,gap_threshold=8",
        "generate_hot_stop_bet:freq_threshold=18,gap_threshold=10",
        "generate_hot_stop_bet:freq_threshold=20,gap_threshold=10",
    ),
    COMPARE_RANDOM_METHOD_ID: (
        "generate_random_5_bets:lottery_type=BIG_LOTTO",
    ),
    SBP_RANDOM_METHOD_ID: (
        "run_baseline_check:inline_random_3bet",
    ),
}
SOURCE_CANDIDATE_TICKET_COUNTS_BY_SOURCE_NATIVE_WAVE6_METHOD: Final = {
    method_id: () for method_id in SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_HOT_STOP_PARAMETER_GRID = (
    (12, 8),
    (12, 10),
    (15, 8),
    (15, 10),
    (15, 12),
    (18, 8),
    (18, 10),
    (20, 10),
)


class LegacySourceNativeWave6Error(ValueError):
    """A request cannot satisfy the sixth source-native batch contract."""


class LegacySourceNativeWave6SourceError(
    LegacySourceNativeWave6Error
):
    """A frozen source produced output outside its preserved contract."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave6Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE6_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave6Metadata:
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
    candidate_k: None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave6Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave6Metadata


def _ticket(numbers: list[int]) -> Ticket:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(
            not _MIN_NUMBER <= number <= _MAX_NUMBER
            for number in values
        )
    ):
        raise LegacySourceNativeWave6SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _validate_request(request: LegacySourceNativeWave6Request) -> None:
    if (
        request.legacy_method_id
        not in SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE6_METHOD
    ):
        raise LegacySourceNativeWave6Error(
            "legacy method is outside the sixth source-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacySourceNativeWave6Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacySourceNativeWave6Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacySourceNativeWave6Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacySourceNativeWave6Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(list(draw.numbers))


def _seed(
    request: LegacySourceNativeWave6Request,
) -> tuple[str, str, int]:
    source_sha256 = SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE6_METHOD[
        request.legacy_method_id
    ]
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE6_PROTOCOL,
            request.legacy_method_id,
            source_sha256,
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _numbers_history(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[tuple[int, ...], ...]:
    return tuple(draw.numbers for draw in history)


def _structural_score(bet: list[int]) -> int:
    total = sum(bet)
    odd = sum(number % 2 == 1 for number in bet)
    zones = [0, 0, 0]
    for number in bet:
        if number <= 16:
            zones[0] += 1
        elif number <= 33:
            zones[1] += 1
        else:
            zones[2] += 1
    consecutive = sum(
        bet[index + 1] - bet[index] == 1
        for index in range(len(bet) - 1)
    )
    spread = bet[-1] - bet[0]
    score = 0
    if 100 <= total <= 200:
        score += 2
    if 120 <= total <= 180:
        score += 2
    if 2 <= odd <= 4:
        score += 2
    if all(zone >= 1 for zone in zones):
        score += 2
    if consecutive <= 1:
        score += 1
    if spread >= 25:
        score += 1
    return score


def _echo_signal_strength(
    history: tuple[tuple[int, ...], ...],
    *,
    max_lag: int = 5,
) -> float:
    if len(history) < max_lag + 1:
        return 0.0
    latest = set(history[-1])
    total_score = 0.0
    maximum_possible = 0.0
    for lag in range(1, max_lag + 1):
        past = set(history[-(lag + 1)])
        overlap = len(latest & past)
        weight = 1.0 / lag
        maximum_possible += _PICK_COUNT * weight
        total_score += overlap * weight
    if maximum_possible == 0:
        return 0.0
    return min(1.0, total_score / maximum_possible)


def _rolling_echo_accuracy(
    history: tuple[tuple[int, ...], ...],
    *,
    lookback: int = 50,
    echo_threshold: float = 0.3,
) -> float:
    if len(history) < lookback + 10:
        return 0.5
    hits = 0
    events = 0
    start = max(10, len(history) - lookback)
    for index in range(start, len(history)):
        echoes = legacy_echo_detector(history[:index], max_lag=5)
        echo_numbers = {
            number
            for number, score in echoes.items()
            if score > echo_threshold
        }
        if echo_numbers:
            events += 1
            if echo_numbers & set(history[index]):
                hits += 1
    if events == 0:
        return 0.5
    return hits / events


def _adaptive_echo_weight(
    history: tuple[tuple[int, ...], ...],
    *,
    base_weight: float = 0.25,
    lookback: int = 50,
) -> tuple[float, float, float]:
    strength = _echo_signal_strength(history)
    accuracy = _rolling_echo_accuracy(
        history,
        lookback=lookback,
    )
    strength_factor = min(1.5, max(0.3, 0.3 + strength * 2.4))
    accuracy_factor = min(1.5, max(0.3, 0.3 + accuracy * 1.7))
    weight = min(
        0.50,
        max(0.05, base_weight * strength_factor * accuracy_factor),
    )
    return weight, strength, accuracy


def _phase2_scores(
    history: tuple[tuple[int, ...], ...],
) -> tuple[
    dict[int, float],
    dict[int, float],
    dict[int, float],
    dict[int, float],
    float,
]:
    temperatures = legacy_continuous_temperature(history, window=50)
    echoes = legacy_echo_detector(history, max_lag=5)
    echo_weight, _strength, _accuracy = _adaptive_echo_weight(
        history,
        lookback=50,
    )
    hot_scores: dict[int, float] = {}
    cold_scores: dict[int, float] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        temperature = temperatures.get(number, 0.5)
        echo = echoes.get(number, 0.0)
        hot_scores[number] = (
            temperature * (1 - echo_weight) + echo * echo_weight
        )
        cold_scores[number] = (
            (1 - temperature) * (1 - echo_weight)
            + echo * echo_weight
        )
    return (
        temperatures,
        echoes,
        hot_scores,
        cold_scores,
        echo_weight,
    )


def _phase2_first_two(
    hot_scores: dict[int, float],
    cold_scores: dict[int, float],
) -> tuple[Ticket, Ticket]:
    hot_ranked = sorted(
        range(_MIN_NUMBER, _MAX_NUMBER + 1),
        key=lambda number: hot_scores[number],
        reverse=True,
    )
    bet1 = _ticket(hot_ranked[:_PICK_COUNT])
    used = set(bet1)
    cold_ranked = sorted(
        range(_MIN_NUMBER, _MAX_NUMBER + 1),
        key=lambda number: cold_scores[number],
        reverse=True,
    )
    bet2 = _ticket(
        [
            number
            for number in cold_ranked
            if number not in used
        ][:_PICK_COUNT]
    )
    return bet1, bet2


def _phase2_echo(
    history: tuple[tuple[int, ...], ...],
) -> tuple[Ticket, ...]:
    (
        temperatures,
        echoes,
        hot_scores,
        cold_scores,
        echo_weight,
    ) = _phase2_scores(history)
    two_bet = _phase2_first_two(hot_scores, cold_scores)
    three_bet_first = _phase2_first_two(hot_scores, cold_scores)
    used = set(three_bet_first[0]) | set(three_bet_first[1])
    bet3_scores: dict[int, float] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        if number in used:
            continue
        temperature = temperatures.get(number, 0.5)
        echo = echoes.get(number, 0.0)
        warm_proximity = 1.0 - abs(temperature - 0.5) * 2.0
        echo_share = min(0.7, echo_weight * 2)
        bet3_scores[number] = (
            echo * echo_share
            + warm_proximity * (1 - echo_share)
        )
    ranked = sorted(
        bet3_scores,
        key=lambda number: bet3_scores[number],
        reverse=True,
    )
    candidates = sorted(ranked[:12])
    if len(candidates) < _PICK_COUNT:
        candidates = [
            number
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
            if number not in used
        ]
    best_bet3: list[int] | None = None
    best_score = -1.0
    if len(candidates) >= _PICK_COUNT:
        for candidate in combinations(candidates, _PICK_COUNT):
            bet = sorted(candidate)
            average_score = (
                sum(bet3_scores.get(number, 0) for number in bet)
                / _PICK_COUNT
            )
            composite = _structural_score(bet) + average_score * 0.1
            if composite > best_score:
                best_score = composite
                best_bet3 = bet
    if best_bet3 is None:
        best_bet3 = sorted(candidates[:_PICK_COUNT])
    return (
        *two_bet,
        *three_bet_first,
        _ticket(best_bet3),
    )


def _hot_stop_statistics(
    history: tuple[tuple[int, ...], ...],
) -> tuple[dict[int, int], dict[int, int]]:
    recent = history[-100:] if len(history) >= 100 else history
    frequency = Counter(
        number for draw in recent for number in draw
    )
    appeared_in_recent = {
        number for draw in history[-10:] for number in draw
    }
    gaps: dict[int, int] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        if number in appeared_in_recent:
            gaps[number] = 0
            continue
        gap = 0
        for draw in reversed(history):
            if number in draw:
                break
            gap += 1
        gaps[number] = gap
    return (
        {
            number: frequency.get(number, 0)
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        },
        gaps,
    )


def _hot_stop_ticket(
    *,
    frequencies: dict[int, int],
    gaps: dict[int, int],
    frequency_threshold: int,
    gap_threshold: int,
) -> Ticket:
    candidates = [
        (number, frequencies[number] * gaps[number])
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
        if frequencies[number] >= frequency_threshold
        and gaps[number] >= gap_threshold
    ]
    candidates.sort(key=lambda item: -item[1])
    result = [number for number, _score in candidates[:_PICK_COUNT]]
    if len(result) < _PICK_COUNT:
        used = set(result)
        frequency_ranked = sorted(
            range(_MIN_NUMBER, _MAX_NUMBER + 1),
            key=lambda number: -frequencies[number],
        )
        for number in frequency_ranked:
            if number not in used:
                result.append(number)
                if len(result) >= _PICK_COUNT:
                    break
    return _ticket(result[:_PICK_COUNT])


def _hot_stop_rebound(
    history: tuple[tuple[int, ...], ...],
) -> tuple[Ticket, ...]:
    frequencies, gaps = _hot_stop_statistics(history)
    return tuple(
        _hot_stop_ticket(
            frequencies=frequencies,
            gaps=gaps,
            frequency_threshold=frequency_threshold,
            gap_threshold=gap_threshold,
        )
        for frequency_threshold, gap_threshold in (
            _HOT_STOP_PARAMETER_GRID
        )
    )


def _random_tickets(
    *,
    seed_integer: int,
    count: int,
) -> tuple[Ticket, ...]:
    rng = random.Random()
    rng.seed(seed_integer, version=2)
    return tuple(
        _ticket(rng.sample(range(_MIN_NUMBER, _MAX_NUMBER + 1), 6))
        for _ in range(count)
    )


def generate_legacy_source_native_wave6_portfolio(
    request: LegacySourceNativeWave6Request,
) -> LegacySourceNativeWave6Result:
    """Generate source-ordered native tickets from strictly prior history."""

    _validate_request(request)
    minimum_history = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE6_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum_history:
        raise LegacySourceNativeWave6Error(
            f"method requires at least {minimum_history} history draws"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    history = _numbers_history(request.history)
    if request.legacy_method_id == ECHO_PHASE2_METHOD_ID:
        tickets = _phase2_echo(history)
    elif request.legacy_method_id == HOT_STOP_REBOUND_METHOD_ID:
        tickets = _hot_stop_rebound(history)
    elif request.legacy_method_id == COMPARE_RANDOM_METHOD_ID:
        tickets = _random_tickets(
            seed_integer=seed_integer,
            count=5,
        )
    else:
        tickets = _random_tickets(
            seed_integer=seed_integer,
            count=3,
        )
    expected_counts = {
        ECHO_PHASE2_METHOD_ID: 5,
        HOT_STOP_REBOUND_METHOD_ID: 8,
        COMPARE_RANDOM_METHOD_ID: 5,
        SBP_RANDOM_METHOD_ID: 3,
    }
    if len(tickets) != expected_counts[request.legacy_method_id]:
        raise LegacySourceNativeWave6SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    random_protocol = RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE6_METHOD[
        request.legacy_method_id
    ]
    return LegacySourceNativeWave6Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave6Metadata(
            protocol=SOURCE_NATIVE_WAVE6_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE6_METHOD[
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
                else (
                    "TARGET_STABLE_SOURCE_CALL_ORDER_PRESERVING_"
                    "VERSIONED_SEED"
                )
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="OLDEST_FIRST",
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE6_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_order=(
                "FROZEN_SOURCE_CONFIGURATION_AND_BET_CALL_ORDER"
            ),
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            source_combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE6_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_candidate_ticket_counts=(),
            candidate_k=None,
            combination_count=None,
        ),
    )


__all__ = [
    "COMPARE_RANDOM_METHOD_ID",
    "DEFAULT_SOURCE_NATIVE_WAVE6_USER_SEED",
    "ECHO_PHASE2_METHOD_ID",
    "HOT_STOP_REBOUND_METHOD_ID",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE6_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE6_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE6_METHOD",
    "SBP_RANDOM_METHOD_ID",
    "SOURCE_CANDIDATE_TICKET_COUNTS_BY_SOURCE_NATIVE_WAVE6_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE6_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE6_METHOD",
    "SOURCE_NATIVE_WAVE6_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE6_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE6_METHODS",
    "LegacySourceNativeWave6Error",
    "LegacySourceNativeWave6Metadata",
    "LegacySourceNativeWave6Request",
    "LegacySourceNativeWave6Result",
    "LegacySourceNativeWave6SourceError",
    "generate_legacy_source_native_wave6_portfolio",
]
