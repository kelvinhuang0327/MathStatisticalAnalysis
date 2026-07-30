"""Faithful ports of the third frozen BIG_LOTTO history-native batch."""

from __future__ import annotations

import hashlib
import random
from collections import Counter
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
    LegacyNumpyRandomState,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

HISTORY_NATIVE_WAVE3_PROTOCOL = "legacy_history_native_wave3/v1"
DEFAULT_HISTORY_NATIVE_WAVE3_USER_SEED = (
    "biglotto-full-universe-history-native-wave3-v1"
)
CORE_SATELLITE_METHOD_ID = "lottery_api/engine/core_satellite.py"
NEGATIVE_SELECTION_METHOD_ID = (
    "lottery_api/models/negative_selection_biglotto.py"
)
QUANTUM_RANDOM_METHOD_ID = (
    "lottery_api/models/quantum_random_predictor.py"
)
SUPPORTED_HISTORY_NATIVE_WAVE3_METHODS = (
    CORE_SATELLITE_METHOD_ID,
    NEGATIVE_SELECTION_METHOD_ID,
    QUANTUM_RANDOM_METHOD_ID,
)
SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE3_METHOD: Final = {
    CORE_SATELLITE_METHOD_ID: (
        "2e82891003b36fa3dbb6ddcb2c898c3366da013257ad808ea5bbf5a672e07350"
    ),
    NEGATIVE_SELECTION_METHOD_ID: (
        "98f860c52cc2f01552690b7903679961a263909fae844896860442909dca1294"
    ),
    QUANTUM_RANDOM_METHOD_ID: (
        "7e310d6577c111b260b1c9ad4f3e218f38910dcd92a874247716d8dc269c9926"
    ),
}
MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE3_METHOD: Final = {
    method_id: 1 for method_id in SUPPORTED_HISTORY_NATIVE_WAVE3_METHODS
}
NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE3_METHOD: Final = {
    CORE_SATELLITE_METHOD_ID: (
        "FOUR_DOCUMENTED_HISTORY_MODES_X_3_SOURCE_ORDER_TICKETS"
    ),
    NEGATIVE_SELECTION_METHOD_ID: (
        "BASE_4_THEN_ENHANCED_UP_TO_4_SOURCE_ORDER_TICKETS"
    ),
    QUANTUM_RANDOM_METHOD_ID: "EXACTLY_8_DIVERSITY_ORDERED_TICKETS",
}
RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE3_METHOD: Final = {
    CORE_SATELLITE_METHOD_ID: "NONE_DETERMINISTIC",
    NEGATIVE_SELECTION_METHOD_ID: (
        "numpy.random.RandomState(MT19937)+random.Random(MT19937)_fallback"
    ),
    QUANTUM_RANDOM_METHOD_ID: (
        "random.Random(MT19937)_VERSIONED_REPLACEMENT_FOR_UNPRESERVED_QRNG_OR_SECRETS"
    ),
}
SOURCE_COMBINATION_COUNT_BY_HISTORY_NATIVE_WAVE3_METHOD: Final = {
    CORE_SATELLITE_METHOD_ID: 4,
    NEGATIVE_SELECTION_METHOD_ID: 2,
    QUANTUM_RANDOM_METHOD_ID: None,
}
SOURCE_COMBINATION_MEMBERS_BY_HISTORY_NATIVE_WAVE3_METHOD: Final = {
    CORE_SATELLITE_METHOD_ID: (
        "generate_from_history:mid_frequency",
        "generate_from_history:hot",
        "generate_from_history:cold",
        "generate_from_history:balanced",
    ),
    NEGATIVE_SELECTION_METHOD_ID: (
        "negative_selection_predict:num_bets=4",
        "enhanced_negative_predict:num_bets=4",
    ),
    QUANTUM_RANDOM_METHOD_ID: (
        "generate_8_bets:ensure_diversity=True",
    ),
}
SOURCE_CANDIDATE_TICKET_COUNTS_BY_HISTORY_NATIVE_WAVE3_METHOD: Final = {
    CORE_SATELLITE_METHOD_ID: (),
    NEGATIVE_SELECTION_METHOD_ID: (400, 200),
    QUANTUM_RANDOM_METHOD_ID: (),
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_CORE_MODES = ("mid_frequency", "hot", "cold", "balanced")


class LegacyHistoryNativeWave3Error(ValueError):
    """A request cannot satisfy the third history-native batch contract."""


class LegacyHistoryNativeWave3SourceError(
    LegacyHistoryNativeWave3Error
):
    """A frozen source produced output outside its preserved contract."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacyHistoryNativeWave3Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_HISTORY_NATIVE_WAVE3_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacyHistoryNativeWave3Metadata:
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
class LegacyHistoryNativeWave3Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacyHistoryNativeWave3Metadata


def _ticket(numbers: list[int]) -> Ticket:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(not _MIN_NUMBER <= number <= _MAX_NUMBER for number in values)
    ):
        raise LegacyHistoryNativeWave3SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _validate_request(request: LegacyHistoryNativeWave3Request) -> None:
    if (
        request.legacy_method_id
        not in SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE3_METHOD
    ):
        raise LegacyHistoryNativeWave3Error(
            "legacy method is outside the third history-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacyHistoryNativeWave3Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacyHistoryNativeWave3Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacyHistoryNativeWave3Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacyHistoryNativeWave3Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(list(draw.numbers))


def _seed(
    request: LegacyHistoryNativeWave3Request,
) -> tuple[str, str, int]:
    source_sha256 = SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE3_METHOD[
        request.legacy_method_id
    ]
    material = "|".join(
        (
            HISTORY_NATIVE_WAVE3_PROTOCOL,
            request.legacy_method_id,
            source_sha256,
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _core_satellite_pool(
    history: tuple[LegacyHistoryDraw, ...],
    method: str,
) -> list[int]:
    recent = history[-30:] if len(history) > 30 else history
    frequency = Counter(
        number for draw in recent for number in draw.numbers
    )
    all_numbers = list(range(_MIN_NUMBER, _MAX_NUMBER + 1))
    if method == "hot":
        return sorted(
            all_numbers,
            key=lambda number: frequency.get(number, 0),
            reverse=True,
        )
    if method == "cold":
        return sorted(
            all_numbers,
            key=lambda number: frequency.get(number, 0),
        )
    if method == "balanced":
        hot = sorted(
            all_numbers,
            key=lambda number: frequency.get(number, 0),
            reverse=True,
        )
        cold = sorted(
            all_numbers,
            key=lambda number: frequency.get(number, 0),
        )
        pool: list[int] = []
        for hot_number, cold_number in zip(hot, cold, strict=True):
            if hot_number not in pool:
                pool.append(hot_number)
            if cold_number not in pool:
                pool.append(cold_number)
        return pool
    expected = 30 * _PICK_COUNT / _MAX_NUMBER
    return sorted(
        all_numbers,
        key=lambda number: abs(frequency.get(number, 0) - expected),
    )


def _core_satellite_generate(pool: list[int]) -> tuple[Ticket, ...]:
    anchors = pool[:3]
    anchor_set = set(anchors)
    satellite_candidates = [
        number for number in pool if number not in anchor_set
    ]
    satellites: list[list[int]] = []
    used: set[int] = set()
    for _ in range(3):
        bet_satellites: list[int] = []
        for number in satellite_candidates:
            if number not in used and len(bet_satellites) < 3:
                bet_satellites.append(number)
                used.add(number)
        satellites.append(sorted(bet_satellites))
    return tuple(
        _ticket(list(set(anchors) | set(satellites_for_bet)))
        for satellites_for_bet in satellites
    )


def _core_satellite(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[Ticket, ...]:
    return tuple(
        ticket
        for mode in _CORE_MODES
        for ticket in _core_satellite_generate(
            _core_satellite_pool(history, mode)
        )
    )


def _negative_candidate_pool(
    history: tuple[LegacyHistoryDraw, ...],
) -> set[int]:
    all_numbers = set(range(_MIN_NUMBER, _MAX_NUMBER + 1))
    recent_frequency = Counter(
        number for draw in history[-10:] for number in draw.numbers
    )
    long_frequency = Counter(
        number for draw in history[-100:] for number in draw.numbers
    )
    exclude_hot = {
        number
        for number, count in recent_frequency.items()
        if count >= 3
    }
    exclude_cold = {
        number
        for number in all_numbers
        if long_frequency.get(number, 0) < 3
    }
    candidate_pool = all_numbers - exclude_hot - exclude_cold
    if len(candidate_pool) < 20:
        candidate_pool = all_numbers - exclude_hot
    return candidate_pool


def _negative_generate_candidates(
    pool: set[int],
    history: tuple[LegacyHistoryDraw, ...],
    num_candidates: int,
    numpy_rng: LegacyNumpyRandomState,
) -> list[list[int]]:
    pool_list = list(pool)
    long_frequency = Counter(
        number for draw in history[-100:] for number in draw.numbers
    )
    average_frequency = (
        sum(long_frequency.values()) / len(long_frequency)
        if long_frequency
        else 1
    )
    weights = {
        number: 1.0
        + max(
            0.0,
            (
                average_frequency - long_frequency.get(number, 0)
            )
            / average_frequency
            * 0.5,
        )
        for number in pool_list
    }
    total_weight = sum(weights.values())
    probabilities = [
        weights[number] / total_weight for number in pool_list
    ]
    return [
        sorted(
            numpy_rng.choice_without_replacement(
                pool_list,
                _PICK_COUNT,
                probabilities=probabilities,
            )
        )
        for _ in range(num_candidates)
    ]


def _negative_structural_filter(
    candidates: list[list[int]],
) -> list[list[int]]:
    filtered: list[list[int]] = []
    for numbers in candidates:
        zones = [0, 0, 0]
        for number in numbers:
            if number <= 16:
                zones[0] += 1
            elif number <= 33:
                zones[1] += 1
            else:
                zones[2] += 1
        if max(zones) >= 5 or min(zones) == 0:
            continue
        odd_count = sum(number % 2 == 1 for number in numbers)
        if odd_count <= 1 or odd_count >= 5:
            continue
        total = sum(numbers)
        if total < 100 or total > 200:
            continue
        maximum_consecutive = 1
        current_consecutive = 1
        for index in range(1, len(numbers)):
            if numbers[index] - numbers[index - 1] == 1:
                current_consecutive += 1
                maximum_consecutive = max(
                    maximum_consecutive,
                    current_consecutive,
                )
            else:
                current_consecutive = 1
        if maximum_consecutive >= 4:
            continue
        filtered.append(numbers)
    if len(filtered) < 10:
        return candidates[:100]
    return filtered


def _negative_select_best(
    candidates: list[list[int]],
    num_bets: int,
) -> list[list[int]]:
    if len(candidates) <= num_bets:
        return candidates
    selected = [candidates[0]]
    for _ in range(num_bets - 1):
        best_candidate: list[int] | None = None
        best_diversity = -1
        for candidate in candidates:
            if candidate in selected:
                continue
            minimum_difference = min(
                len(set(candidate) - set(existing))
                for existing in selected
            )
            if minimum_difference > best_diversity:
                best_diversity = minimum_difference
                best_candidate = candidate
        if best_candidate is not None:
            selected.append(best_candidate)
    return selected


def _negative_base(
    history: tuple[LegacyHistoryDraw, ...],
    num_bets: int,
    numpy_rng: LegacyNumpyRandomState,
) -> list[list[int]]:
    pool = _negative_candidate_pool(history)
    candidates = _negative_generate_candidates(
        pool,
        history,
        num_bets * 100,
        numpy_rng,
    )
    return _negative_select_best(
        _negative_structural_filter(candidates),
        num_bets,
    )


def _negative_cluster(
    history: tuple[LegacyHistoryDraw, ...],
    num_bets: int,
) -> list[list[int]]:
    cooccurrence: Counter[tuple[int, int]] = Counter()
    for draw in history[-100:]:
        cooccurrence.update(combinations(sorted(draw.numbers), 2))
    number_scores: Counter[int] = Counter()
    for (first, second), count in cooccurrence.items():
        number_scores[first] += count
        number_scores[second] += count
    centers = [
        number
        for number, _count in number_scores.most_common(num_bets)
    ]
    predictions: list[list[int]] = []
    used: set[tuple[int, ...]] = set()
    for anchor in centers:
        candidates: Counter[int] = Counter()
        for (first, second), count in cooccurrence.items():
            if first == anchor:
                candidates[second] += count
            elif second == anchor:
                candidates[first] += count
        selected = [anchor]
        for number, _count in candidates.most_common(_PICK_COUNT - 1):
            if number not in selected:
                selected.append(number)
            if len(selected) >= _PICK_COUNT:
                break
        while len(selected) < _PICK_COUNT:
            for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
                if number not in selected:
                    selected.append(number)
                    break
        prediction = sorted(selected[:_PICK_COUNT])
        identity = tuple(prediction)
        if identity not in used:
            predictions.append(prediction)
            used.add(identity)
    return predictions[:num_bets]


def _negative_selection(
    history: tuple[LegacyHistoryDraw, ...],
    seed_integer: int,
) -> tuple[Ticket, ...]:
    numpy_rng = LegacyNumpyRandomState(seed_integer % (2**32))
    base = _negative_base(history, 4, numpy_rng)
    enhanced_negative = _negative_base(history, 2, numpy_rng)
    enhanced = list(enhanced_negative)
    for prediction in _negative_cluster(history, 2):
        if prediction not in enhanced:
            enhanced.append(prediction)
    return tuple(
        _ticket(numbers)
        for numbers in [*base, *enhanced[:4]]
    )


def _quantum_random(
    seed_integer: int,
) -> tuple[Ticket, ...]:
    rng = random.Random()
    rng.seed(seed_integer, version=2)

    def sample() -> list[int]:
        numbers: set[int] = set()
        while len(numbers) < _PICK_COUNT:
            numbers.add(rng.randrange(_MAX_NUMBER) + 1)
        return sorted(numbers)

    tickets: list[Ticket] = []
    all_numbers_used: set[int] = set()
    for bet_index in range(8):
        if bet_index == 0:
            numbers = sample()
        else:
            best_bet: list[int] | None = None
            minimum_overlap = float("inf")
            for _ in range(50):
                candidate = sample()
                overlap = len(set(candidate) & all_numbers_used)
                if overlap < minimum_overlap:
                    minimum_overlap = overlap
                    best_bet = candidate
                if overlap == 0:
                    break
            numbers = best_bet if best_bet is not None else sample()
        all_numbers_used.update(numbers)
        tickets.append(_ticket(numbers))
    return tuple(tickets)


def generate_legacy_history_native_wave3_portfolio(
    request: LegacyHistoryNativeWave3Request,
) -> LegacyHistoryNativeWave3Result:
    """Generate source-ordered native tickets from strictly prior history."""

    _validate_request(request)
    minimum_history = MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE3_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum_history:
        raise LegacyHistoryNativeWave3Error(
            f"method requires at least {minimum_history} history draws"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    if request.legacy_method_id == CORE_SATELLITE_METHOD_ID:
        tickets = _core_satellite(request.history)
    elif request.legacy_method_id == NEGATIVE_SELECTION_METHOD_ID:
        tickets = _negative_selection(request.history, seed_integer)
    else:
        tickets = _quantum_random(seed_integer)
    if not tickets or len(tickets) > 12:
        raise LegacyHistoryNativeWave3SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    expected_counts = {
        CORE_SATELLITE_METHOD_ID: 12,
        QUANTUM_RANDOM_METHOD_ID: 8,
    }
    expected = expected_counts.get(request.legacy_method_id)
    if expected is not None and len(tickets) != expected:
        raise LegacyHistoryNativeWave3SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    if (
        request.legacy_method_id == NEGATIVE_SELECTION_METHOD_ID
        and not 6 <= len(tickets) <= 8
    ):
        raise LegacyHistoryNativeWave3SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    random_protocol = RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE3_METHOD[
        request.legacy_method_id
    ]
    return LegacyHistoryNativeWave3Result(
        tickets=tickets,
        metadata=LegacyHistoryNativeWave3Metadata(
            protocol=HISTORY_NATIVE_WAVE3_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE3_METHOD[
                request.legacy_method_id
            ],
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
                if request.legacy_method_id == CORE_SATELLITE_METHOD_ID
                else (
                    "TARGET_STABLE_SOURCE_CALL_ORDER_PRESERVING_SEED"
                )
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order="OLDEST_FIRST",
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE3_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_order=(
                "FROZEN_SOURCE_ENTRYPOINT_AND_BET_ORDER"
            ),
            native_duplicate_ticket_count=len(tickets) - len(set(tickets)),
            source_combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_HISTORY_NATIVE_WAVE3_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_candidate_ticket_counts=(
                SOURCE_CANDIDATE_TICKET_COUNTS_BY_HISTORY_NATIVE_WAVE3_METHOD[
                    request.legacy_method_id
                ]
            ),
            candidate_k=None,
            combination_count=None,
        ),
    )


__all__ = [
    "CORE_SATELLITE_METHOD_ID",
    "DEFAULT_HISTORY_NATIVE_WAVE3_USER_SEED",
    "HISTORY_NATIVE_WAVE3_PROTOCOL",
    "MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE3_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE3_METHOD",
    "NEGATIVE_SELECTION_METHOD_ID",
    "QUANTUM_RANDOM_METHOD_ID",
    "RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE3_METHOD",
    "SOURCE_CANDIDATE_TICKET_COUNTS_BY_HISTORY_NATIVE_WAVE3_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_HISTORY_NATIVE_WAVE3_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_HISTORY_NATIVE_WAVE3_METHOD",
    "SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE3_METHOD",
    "SUPPORTED_HISTORY_NATIVE_WAVE3_METHODS",
    "LegacyHistoryNativeWave3Error",
    "LegacyHistoryNativeWave3Metadata",
    "LegacyHistoryNativeWave3Request",
    "LegacyHistoryNativeWave3Result",
    "LegacyHistoryNativeWave3SourceError",
    "generate_legacy_history_native_wave3_portfolio",
]
