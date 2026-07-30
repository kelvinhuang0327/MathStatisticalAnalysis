"""Faithful ports of the fifth frozen BIG_LOTTO history-native batch."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

HISTORY_NATIVE_WAVE5_PROTOCOL = "legacy_history_native_wave5/v1"
DEFAULT_HISTORY_NATIVE_WAVE5_USER_SEED = (
    "biglotto-full-universe-history-native-wave5-v1"
)
MODERATE_SELECTION_METHOD_ID = "tools/backtest_moderate_selection.py"
DIVERSIFIED_2BET_METHOD_ID = "tools/backtest_diversified_2bet.py"
ECHO_2BET_METHOD_ID = "tools/predict_biglotto_echo_2bet.py"
SUPPORTED_HISTORY_NATIVE_WAVE5_METHODS = (
    MODERATE_SELECTION_METHOD_ID,
    DIVERSIFIED_2BET_METHOD_ID,
    ECHO_2BET_METHOD_ID,
)
SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE5_METHOD: Final = {
    MODERATE_SELECTION_METHOD_ID: (
        "ab873585689fac7c7172aef9748b815c62474be8fde62cb7b8186fe243688395"
    ),
    DIVERSIFIED_2BET_METHOD_ID: (
        "78b1d5f5121ce5fb5786975cfaf893bd62e8b35ea088b2d6dcd469f426b5e7f5"
    ),
    ECHO_2BET_METHOD_ID: (
        "59c20b25b1fa59ef9edad2a6a6c031321bfbafea7752351c692ab5cfa2fa6620"
    ),
}
MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE5_METHOD: Final = {
    MODERATE_SELECTION_METHOD_ID: 10,
    DIVERSIFIED_2BET_METHOD_ID: 30,
    ECHO_2BET_METHOD_ID: 1,
}
NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE5_METHOD: Final = {
    MODERATE_SELECTION_METHOD_ID: (
        "SINGLE_MODE_1_THEN_TWO_BET_MODE_2_SOURCE_ORDER_TICKETS"
    ),
    DIVERSIFIED_2BET_METHOD_ID: (
        "FIVE_SOURCE_CONFIGURATIONS_FLATTENED_TO_8_POSITIONAL_TICKETS"
    ),
    ECHO_2BET_METHOD_ID: "HOT_ECHO_THEN_DISJOINT_COLD_ECHO_2_TICKETS",
}
RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE5_METHOD: Final = {
    method_id: "NONE_DETERMINISTIC"
    for method_id in SUPPORTED_HISTORY_NATIVE_WAVE5_METHODS
}
SOURCE_COMBINATION_COUNT_BY_HISTORY_NATIVE_WAVE5_METHOD: Final = {
    MODERATE_SELECTION_METHOD_ID: 2,
    DIVERSIFIED_2BET_METHOD_ID: 5,
    ECHO_2BET_METHOD_ID: None,
}
SOURCE_COMBINATION_MEMBERS_BY_HISTORY_NATIVE_WAVE5_METHOD: Final = {
    MODERATE_SELECTION_METHOD_ID: (
        "moderate_selection_strategy:last_draw_penalty=0.15",
        "moderate_selection_2bet",
    ),
    DIVERSIFIED_2BET_METHOD_ID: (
        "single:strategy_moderate_hot",
        "single:strategy_comeback",
        "single:strategy_zone_balance",
        "diversified_2bet",
        "diversified_3bet",
    ),
    ECHO_2BET_METHOD_ID: (
        "echo_aware_deviation_2bet:window=50,echo_weight=0.25",
    ),
}
SOURCE_CANDIDATE_TICKET_COUNTS_BY_HISTORY_NATIVE_WAVE5_METHOD: Final = {
    method_id: () for method_id in SUPPORTED_HISTORY_NATIVE_WAVE5_METHODS
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6


class LegacyHistoryNativeWave5Error(ValueError):
    """A request cannot satisfy the fifth history-native batch contract."""


class LegacyHistoryNativeWave5SourceError(
    LegacyHistoryNativeWave5Error
):
    """A frozen source produced output outside its preserved contract."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacyHistoryNativeWave5Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_HISTORY_NATIVE_WAVE5_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacyHistoryNativeWave5Metadata:
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
class LegacyHistoryNativeWave5Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacyHistoryNativeWave5Metadata


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
        raise LegacyHistoryNativeWave5SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _validate_request(request: LegacyHistoryNativeWave5Request) -> None:
    if (
        request.legacy_method_id
        not in SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE5_METHOD
    ):
        raise LegacyHistoryNativeWave5Error(
            "legacy method is outside the fifth history-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacyHistoryNativeWave5Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacyHistoryNativeWave5Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacyHistoryNativeWave5Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacyHistoryNativeWave5Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(list(draw.numbers))


def _seed(
    request: LegacyHistoryNativeWave5Request,
) -> tuple[str, str, int]:
    source_sha256 = SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE5_METHOD[
        request.legacy_method_id
    ]
    material = "|".join(
        (
            HISTORY_NATIVE_WAVE5_PROTOCOL,
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


def _calculate_gaps(
    history: tuple[tuple[int, ...], ...],
) -> dict[int, int]:
    gaps = {
        number: len(history)
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
    }
    for index, draw in enumerate(reversed(history)):
        for number in draw:
            if gaps[number] == len(history):
                gaps[number] = index
    return gaps


def _calculate_frequency(
    history: tuple[tuple[int, ...], ...],
    *,
    window: int,
) -> Counter[int]:
    frequency: Counter[int] = Counter()
    recent = history[-window:] if len(history) >= window else history
    for draw in recent:
        frequency.update(draw)
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        if number not in frequency:
            frequency[number] = 0
    return frequency


def _moderate_single(
    history: tuple[tuple[int, ...], ...],
) -> Ticket:
    last_draw = set(history[-1])
    gaps = _calculate_gaps(history)
    frequency_30 = _calculate_frequency(history, window=30)
    frequency_50 = _calculate_frequency(history, window=50)
    top_frequency = sorted(
        frequency_30.values(),
        reverse=True,
    )[:3]
    scores: dict[int, float] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        gap = gaps[number]
        frequency30 = frequency_30[number]
        base_score = (
            frequency30 * 2
            + frequency_50[number]
            + gap * 0.5
        )
        if frequency30 in top_frequency and frequency30 > 0:
            base_score *= 0.7
        if gap > 15:
            base_score *= 0.6
        if 8 <= gap <= 12:
            base_score *= 1.3
        if number in last_draw:
            base_score *= 0.15
        scores[number] = base_score
    ranked = sorted(
        scores,
        key=lambda number: scores[number],
        reverse=True,
    )
    return _ticket(ranked[:_PICK_COUNT])


def _moderate_two_bet(
    history: tuple[tuple[int, ...], ...],
) -> tuple[Ticket, Ticket]:
    last_draw = set(history[-1])
    gaps = _calculate_gaps(history)
    frequency_30 = _calculate_frequency(history, window=30)
    frequency_50 = _calculate_frequency(history, window=50)
    top_frequency = sorted(
        frequency_30.values(),
        reverse=True,
    )[:3]
    scores_v1: dict[int, float] = {}
    scores_v2: dict[int, float] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        gap = gaps[number]
        frequency30 = frequency_30[number]
        frequency50 = frequency_50[number]
        base_v1 = frequency30 * 2.5 + frequency50 + gap * 0.3
        base_v2 = frequency30 * 1.5 + frequency50 * 0.8 + gap * 0.8
        if frequency30 in top_frequency and frequency30 > 0:
            base_v1 *= 0.7
            base_v2 *= 0.5
        if gap > 15:
            base_v1 *= 0.6
            base_v2 *= 0.7
        if 8 <= gap <= 12:
            base_v1 *= 1.2
            base_v2 *= 1.4
        if number in last_draw:
            base_v1 *= 0.15
            base_v2 *= 0.15
        scores_v1[number] = base_v1
        scores_v2[number] = base_v2
    ranked_v1 = sorted(
        scores_v1,
        key=lambda number: scores_v1[number],
        reverse=True,
    )
    ranked_v2 = sorted(
        scores_v2,
        key=lambda number: scores_v2[number],
        reverse=True,
    )
    bet1 = _ticket(ranked_v1[:_PICK_COUNT])
    bet2 = _ticket(ranked_v2[:_PICK_COUNT])
    if bet1 == bet2:
        bet2 = _ticket(ranked_v2[1 : _PICK_COUNT + 1])
    return bet1, bet2


def _moderate_selection(
    history: tuple[tuple[int, ...], ...],
) -> tuple[Ticket, ...]:
    two_bet = _moderate_two_bet(history)
    return (_moderate_single(history), *two_bet)


def _diversified_moderate_hot(
    history: tuple[tuple[int, ...], ...],
) -> Ticket:
    last_draw = set(history[-1])
    gaps = _calculate_gaps(history)
    frequency = _calculate_frequency(history, window=30)
    frequency_rank = {
        number: rank
        for rank, number in enumerate(
            sorted(
                frequency,
                key=lambda candidate: frequency[candidate],
                reverse=True,
            ),
            start=1,
        )
    }
    scores: dict[int, float] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        rank = frequency_rank[number]
        gap = gaps[number]
        if 5 <= rank <= 15:
            score = float(100 + (15 - rank) * 5)
        elif rank < 5:
            score = 60.0
        else:
            score = float(80 - rank)
        if gap > 15:
            score *= 0.6
        elif 6 <= gap <= 12:
            score *= 1.2
        if number in last_draw:
            score *= 0.15
        scores[number] = score
    ranked = sorted(
        scores,
        key=lambda number: scores[number],
        reverse=True,
    )
    return _ticket(ranked[:_PICK_COUNT])


def _diversified_comeback(
    history: tuple[tuple[int, ...], ...],
) -> Ticket:
    last_draw = set(history[-1])
    gaps = _calculate_gaps(history)
    frequency = _calculate_frequency(history, window=50)
    average_frequency = sum(frequency.values()) / len(frequency)
    scores: dict[int, float] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        gap = gaps[number]
        if 8 <= gap <= 14:
            gap_score = 100 + (14 - abs(gap - 11)) * 10
        elif 5 <= gap <= 7:
            gap_score = 70
        elif gap > 14:
            gap_score = 50
        else:
            gap_score = 40
        frequency_score = (
            30
            if abs(frequency[number] - average_frequency) < 2
            else 10
        )
        score = float(gap_score + frequency_score)
        if number in last_draw:
            score = 0.0
        scores[number] = score
    ranked = sorted(
        scores,
        key=lambda number: scores[number],
        reverse=True,
    )
    return _ticket(ranked[:_PICK_COUNT])


def _diversified_zone_balance(
    history: tuple[tuple[int, ...], ...],
) -> Ticket:
    last_draw = set(history[-1])
    frequency = _calculate_frequency(history, window=30)
    gaps = _calculate_gaps(history)
    selected: list[int] = []
    for zone in (
        range(1, 17),
        range(17, 34),
        range(34, 50),
    ):
        scores: dict[int, float] = {}
        for number in zone:
            score = frequency[number] * 2 + gaps[number] * 0.5
            if number in last_draw:
                score *= 0.2
            scores[number] = score
        ranked = sorted(
            scores,
            key=lambda number: scores[number],
            reverse=True,
        )
        selected.extend(ranked[:2])
    return _ticket(selected)


def _diversified_selection(
    history: tuple[tuple[int, ...], ...],
) -> tuple[Ticket, ...]:
    hot = _diversified_moderate_hot(history)
    comeback = _diversified_comeback(history)
    zone = _diversified_zone_balance(history)
    return (
        hot,
        comeback,
        zone,
        hot,
        comeback,
        hot,
        comeback,
        zone,
    )


def _echo_detector(
    history: tuple[tuple[int, ...], ...],
    *,
    max_lag: int = 5,
) -> dict[int, float]:
    if len(history) < max_lag + 1:
        return {}
    latest = set(history[-1])
    echo_scores: dict[int, float] = {}
    for lag in range(1, max_lag + 1):
        past = set(history[-(lag + 1)])
        overlap = latest & past
        overlap_count = len(overlap)
        if overlap_count >= 2:
            weight = overlap_count / _PICK_COUNT * (1.0 / lag)
            for number in overlap:
                echo_scores[number] = (
                    echo_scores.get(number, 0.0) + weight * 0.5
                )
            for number in past - latest:
                echo_scores[number] = (
                    echo_scores.get(number, 0.0) + weight
                )
    if echo_scores:
        maximum_score = max(echo_scores.values())
        if maximum_score > 0:
            for number in echo_scores:
                echo_scores[number] /= maximum_score
    return dict(echo_scores)


def _continuous_temperature(
    history: tuple[tuple[int, ...], ...],
    *,
    window: int = 50,
) -> dict[int, float]:
    recent = history[-window:] if len(history) > window else history
    short_window = min(20, len(recent))
    short_recent = (
        history[-short_window:]
        if len(history) > short_window
        else history
    )
    frequency_long: Counter[int] = Counter(
        number for draw in recent for number in draw
    )
    frequency_short: Counter[int] = Counter(
        number for draw in short_recent for number in draw
    )
    gaps: dict[int, int] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        gap = 0
        for draw in reversed(history):
            if number in draw:
                break
            gap += 1
        gaps[number] = gap
    frequency_values = [
        frequency_long.get(number, 0)
        for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
    ]
    frequency_sorted = sorted(frequency_values)
    temperatures: dict[int, float] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        frequency = frequency_long.get(number, 0)
        frequency_component = (
            sum(value <= frequency for value in frequency_sorted)
            / _MAX_NUMBER
        )
        median_gap = _MAX_NUMBER / _PICK_COUNT
        gap_component = math.exp(-gaps[number] / median_gap)
        expected_short = short_window * _PICK_COUNT / _MAX_NUMBER
        expected_long = len(recent) * _PICK_COUNT / _MAX_NUMBER
        short_ratio = frequency_short.get(number, 0) / max(
            expected_short,
            0.1,
        )
        long_ratio = frequency / max(expected_long, 0.1)
        trend_component = min(
            1.0,
            max(0.0, 0.5 + (short_ratio - long_ratio) * 0.5),
        )
        temperatures[number] = (
            0.40 * frequency_component
            + 0.30 * gap_component
            + 0.30 * trend_component
        )
    return temperatures


def legacy_echo_detector(
    history: tuple[tuple[int, ...], ...],
    *,
    max_lag: int = 5,
) -> dict[int, float]:
    """Expose the frozen Echo helper for source files that imported it."""

    return _echo_detector(history, max_lag=max_lag)


def legacy_continuous_temperature(
    history: tuple[tuple[int, ...], ...],
    *,
    window: int = 50,
) -> dict[int, float]:
    """Expose the frozen temperature helper for dependent source files."""

    return _continuous_temperature(history, window=window)


def _echo_aware_selection(
    history: tuple[tuple[int, ...], ...],
) -> tuple[Ticket, Ticket]:
    temperatures = _continuous_temperature(history, window=50)
    echoes = _echo_detector(history, max_lag=5)
    echo_weight = 0.25
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
    hot_ranked = sorted(
        range(_MIN_NUMBER, _MAX_NUMBER + 1),
        key=lambda number: hot_scores[number],
        reverse=True,
    )
    cold_ranked = sorted(
        range(_MIN_NUMBER, _MAX_NUMBER + 1),
        key=lambda number: cold_scores[number],
        reverse=True,
    )
    bet1 = _ticket(hot_ranked[:_PICK_COUNT])
    used = set(bet1)
    bet2 = _ticket(
        [
            number
            for number in cold_ranked
            if number not in used
        ][:_PICK_COUNT]
    )
    return bet1, bet2


def generate_legacy_history_native_wave5_portfolio(
    request: LegacyHistoryNativeWave5Request,
) -> LegacyHistoryNativeWave5Result:
    """Generate source-ordered native tickets from strictly prior history."""

    _validate_request(request)
    minimum_history = MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE5_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum_history:
        raise LegacyHistoryNativeWave5Error(
            f"method requires at least {minimum_history} history draws"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    history = _numbers_history(request.history)
    if request.legacy_method_id == MODERATE_SELECTION_METHOD_ID:
        tickets = _moderate_selection(history)
    elif request.legacy_method_id == DIVERSIFIED_2BET_METHOD_ID:
        tickets = _diversified_selection(history)
    else:
        tickets = _echo_aware_selection(history)
    expected_counts = {
        MODERATE_SELECTION_METHOD_ID: 3,
        DIVERSIFIED_2BET_METHOD_ID: 8,
        ECHO_2BET_METHOD_ID: 2,
    }
    if len(tickets) != expected_counts[request.legacy_method_id]:
        raise LegacyHistoryNativeWave5SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    return LegacyHistoryNativeWave5Result(
        tickets=tickets,
        metadata=LegacyHistoryNativeWave5Metadata(
            protocol=HISTORY_NATIVE_WAVE5_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(
                SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE5_METHOD[
                    request.legacy_method_id
                ]
            ),
            target_draw_number=request.target_draw_number,
            replicate_id=request.replicate_id,
            user_seed=request.user_seed,
            seed_material=seed_material,
            seed_digest=seed_digest,
            seed_integer=seed_integer,
            random_protocol="NONE_DETERMINISTIC",
            randomness_used=False,
            randomness_reproduction="SOURCE_DETERMINISTIC",
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="OLDEST_FIRST",
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE5_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_order=(
                "FROZEN_SOURCE_ENTRYPOINT_AND_BET_ORDER"
            ),
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            source_combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_HISTORY_NATIVE_WAVE5_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_candidate_ticket_counts=(),
            candidate_k=None,
            combination_count=None,
        ),
    )


__all__ = [
    "DEFAULT_HISTORY_NATIVE_WAVE5_USER_SEED",
    "DIVERSIFIED_2BET_METHOD_ID",
    "ECHO_2BET_METHOD_ID",
    "HISTORY_NATIVE_WAVE5_PROTOCOL",
    "MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE5_METHOD",
    "MODERATE_SELECTION_METHOD_ID",
    "NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE5_METHOD",
    "RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE5_METHOD",
    "SOURCE_CANDIDATE_TICKET_COUNTS_BY_HISTORY_NATIVE_WAVE5_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_HISTORY_NATIVE_WAVE5_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_HISTORY_NATIVE_WAVE5_METHOD",
    "SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE5_METHOD",
    "SUPPORTED_HISTORY_NATIVE_WAVE5_METHODS",
    "LegacyHistoryNativeWave5Error",
    "LegacyHistoryNativeWave5Metadata",
    "LegacyHistoryNativeWave5Request",
    "LegacyHistoryNativeWave5Result",
    "LegacyHistoryNativeWave5SourceError",
    "generate_legacy_history_native_wave5_portfolio",
    "legacy_continuous_temperature",
    "legacy_echo_detector",
]
