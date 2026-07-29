"""Faithful ports of the seventeenth frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
import random
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE17_PROTOCOL = "legacy_source_native_wave17/v1"
DEFAULT_SOURCE_NATIVE_WAVE17_USER_SEED = (
    "biglotto-full-universe-source-native-wave17-v1"
)
SCIENTIFIC_SMART_RANDOM_METHOD_ID = (
    "tools/scientific_baseline_report.py"
)
SMART_MULTI_BET_METHOD_ID = "lottery_api/models/smart_multi_bet.py"
SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS = (
    SCIENTIFIC_SMART_RANDOM_METHOD_ID,
    SMART_MULTI_BET_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE17_METHOD: Final = {
    SCIENTIFIC_SMART_RANDOM_METHOD_ID: (
        "a638f456eb66aaa244986dba923dcd7eea704a846a790a8d8f8c30480a800377"
    ),
    SMART_MULTI_BET_METHOD_ID: (
        "613c62c1f1929903e5d58309fccd9a7fd7c755be15d188cf9ab01ffe43f092e9"
    ),
}
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE17_METHOD: Final = {
    SCIENTIFIC_SMART_RANDOM_METHOD_ID: (
        (
            "lottery_api/models/main_optimizer.py",
            "b24a0435994197e627fbaef6775574eff4b51a70c5af49b114196b799882b5dc",
        ),
        (
            "lottery_api/requirements.txt",
            "2046dd0aa9cc084352a2fb1a664e032fba23ac81f0b1e7d3f1d70ff9d1a1e130",
        ),
    ),
    SMART_MULTI_BET_METHOD_ID: (
        (
            "lottery_api/requirements.txt",
            "2046dd0aa9cc084352a2fb1a664e032fba23ac81f0b1e7d3f1d70ff9d1a1e130",
        ),
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE17_METHOD: Final = {
    SCIENTIFIC_SMART_RANDOM_METHOD_ID: 1,
    SMART_MULTI_BET_METHOD_ID: 1,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE17_METHOD: Final = {
    SCIENTIFIC_SMART_RANDOM_METHOD_ID: (
        "SEVEN_NORMATIVE_DIVERSE_SMART_RANDOM_TICKETS_EV_SORTED"
    ),
    SMART_MULTI_BET_METHOD_ID: (
        "SIX_COMPLEMENTARY_POOL_STRATEGY_TICKETS_IN_DECLARATION_ORDER"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE17_METHOD: Final = {
    method_id: (
        "random.Random(MT19937)_TARGET_STABLE_REPLACEMENT_FOR_"
        "UNPRESERVED_MODULE_GLOBAL_STATE"
    )
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE17_METHOD: Final = {
    SCIENTIFIC_SMART_RANDOM_METHOD_ID: 1,
    SMART_MULTI_BET_METHOD_ID: 6,
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE17_METHOD: Final = {
    SCIENTIFIC_SMART_RANDOM_METHOD_ID: (
        "generate_honest_report:BIG_LOTTO:generate_smart_bets(count=7)",
    ),
    SMART_MULTI_BET_METHOD_ID: (
        "hot_dominant",
        "balanced",
        "cold_comeback",
        "consecutive",
        "zone_coverage",
        "constrained",
    ),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE17_METHOD: Final = {
    SCIENTIFIC_SMART_RANDOM_METHOD_ID: "OLDEST_FIRST",
    SMART_MULTI_BET_METHOD_ID: "RECENT_FIRST",
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6


class LegacySourceNativeWave17Error(ValueError):
    """A request cannot satisfy the seventeenth source-native contract."""


class LegacySourceNativeWave17SourceError(
    LegacySourceNativeWave17Error
):
    """The frozen source emitted no valid native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave17Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE17_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave17Metadata:
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
    frozen_support_artifacts: tuple[tuple[str, str], ...]
    source_runtime_parameters: tuple[str, ...]
    candidate_k: None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave17Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave17Metadata


def _ticket(numbers: list[int]) -> Ticket:
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
        raise LegacySourceNativeWave17SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _validate_request(request: LegacySourceNativeWave17Request) -> None:
    if request.legacy_method_id not in (
        SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS
    ):
        raise LegacySourceNativeWave17Error(
            "legacy method is outside the seventeenth source-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacySourceNativeWave17Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacySourceNativeWave17Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacySourceNativeWave17Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacySourceNativeWave17Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(list(draw.numbers))


def _seed(
    request: LegacySourceNativeWave17Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE17_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE17_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _is_normative(numbers: list[int]) -> bool:
    total_sum = sum(numbers)
    if total_sum < 90 or total_sum > 210:
        return False
    odds = sum(1 for number in numbers if number % 2 != 0)
    if odds == 0 or odds == 6:
        return False
    midpoint = _MAX_NUMBER / 2
    lows = sum(1 for number in numbers if number <= midpoint)
    if lows == 0 or lows == 6:
        return False
    sorted_numbers = sorted(numbers)
    consecutive_count = sum(
        1
        for index in range(len(sorted_numbers) - 1)
        if sorted_numbers[index + 1] - sorted_numbers[index] == 1
    )
    return consecutive_count <= 2


def _ev_score(numbers: list[int]) -> float:
    consensus_count = sum(1 for number in numbers if number <= 31)
    unpopular_count = sum(1 for number in numbers if number > 31)
    return (
        100.0
        - (consensus_count**1.5) * 5
        + unpopular_count * 10
    )


def _scientific_smart_random(
    rng: random.Random,
) -> tuple[Ticket, ...]:
    bets: list[list[int]] = []
    attempts = 0
    while len(bets) < 7 and attempts < 1000:
        candidate = sorted(
            rng.sample(
                range(_MIN_NUMBER, _MAX_NUMBER + 1),
                _PICK_COUNT,
            )
        )
        attempts += 1
        if not _is_normative(candidate):
            continue
        if any(
            len(set(candidate) & set(existing)) >= 4
            for existing in bets
        ):
            continue
        bets.append(candidate)
    bets.sort(key=_ev_score, reverse=True)
    return tuple(_ticket(bet) for bet in bets[:7])


def _build_smart_multi_pool(
    history: tuple[LegacyHistoryDraw, ...],
) -> dict[str, list[int]]:
    recent_first = tuple(reversed(history[-300:]))
    frequency: Counter[int] = Counter()
    for draw in recent_first[:50]:
        frequency.update(draw.numbers)
    recent_frequency: Counter[int] = Counter()
    for draw in recent_first[:20]:
        recent_frequency.update(draw.numbers)

    all_numbers = list(range(_MIN_NUMBER, _MAX_NUMBER + 1))
    hot_numbers = [
        number for number, _count in frequency.most_common(15)
    ]
    cold_numbers = [
        number
        for number, _count in frequency.most_common()[-15:]
    ]
    mid_numbers = [
        number
        for number in all_numbers
        if number not in hot_numbers and number not in cold_numbers
    ]
    recent_active = [
        number
        for number, count in recent_frequency.items()
        if count >= 2
    ]
    last_numbers = (
        list(recent_first[0].numbers) if recent_first else []
    )

    comeback: list[tuple[int, float]] = []
    for number in all_numbers:
        current_gap = len(recent_first)
        for index, draw in enumerate(recent_first):
            if number in draw.numbers:
                current_gap = index
                break
        appearances = [
            index
            for index, draw in enumerate(recent_first)
            if number in draw.numbers
        ]
        if len(appearances) < 3:
            continue
        gaps = [
            appearances[index + 1] - appearances[index]
            for index in range(len(appearances) - 1)
        ]
        average_gap = sum(gaps) / len(gaps)
        if current_gap >= average_gap * 0.9:
            comeback.append((number, current_gap / average_gap))
    comeback.sort(key=lambda item: -item[1])
    return {
        "all": all_numbers,
        "cold": cold_numbers,
        "comeback": [item[0] for item in comeback[:15]],
        "hot": hot_numbers,
        "last_draw": last_numbers,
        "mid": mid_numbers,
        "recent_active": recent_active,
    }


def _sample_up_to(
    rng: random.Random,
    candidates: list[int],
    count: int,
) -> list[int]:
    return rng.sample(candidates, min(count, len(candidates)))


def _smart_hot_dominant(
    rng: random.Random,
    pool: dict[str, list[int]],
    used: set[int],
) -> list[int]:
    result = _sample_up_to(
        rng,
        [number for number in pool["hot"] if number not in used],
        4,
    )
    mid_candidates = [
        number
        for number in pool["mid"]
        if number not in used and number not in result
    ]
    result.extend(
        _sample_up_to(rng, mid_candidates, _PICK_COUNT - len(result))
    )
    if len(result) < _PICK_COUNT:
        remaining = [
            number
            for number in pool["all"]
            if number not in result
        ]
        result.extend(
            rng.sample(remaining, _PICK_COUNT - len(result))
        )
    return result[:_PICK_COUNT]


def _smart_balanced(
    rng: random.Random,
    pool: dict[str, list[int]],
    used: set[int],
) -> list[int]:
    result: list[int] = []
    for category, count in (("hot", 2), ("mid", 2), ("cold", 2)):
        candidates = [
            number
            for number in pool[category]
            if number not in used and number not in result
        ]
        result.extend(_sample_up_to(rng, candidates, count))
    if len(result) < _PICK_COUNT:
        remaining = [
            number
            for number in pool["all"]
            if number not in result
        ]
        result.extend(
            rng.sample(remaining, _PICK_COUNT - len(result))
        )
    return result[:_PICK_COUNT]


def _smart_cold_comeback(
    rng: random.Random,
    pool: dict[str, list[int]],
    used: set[int],
) -> list[int]:
    result = [
        number
        for number in pool["comeback"]
        if number not in used
    ][:4]
    hot = [
        number
        for number in pool["hot"]
        if number not in used and number not in result
    ]
    result.extend(hot[: _PICK_COUNT - len(result)])
    if len(result) < _PICK_COUNT:
        remaining = [
            number
            for number in pool["all"]
            if number not in result
        ]
        result.extend(
            rng.sample(remaining, _PICK_COUNT - len(result))
        )
    return result[:_PICK_COUNT]


def _smart_consecutive(
    rng: random.Random,
    pool: dict[str, list[int]],
    used: set[int],
) -> list[int]:
    result = [
        number
        for number in pool["last_draw"]
        if number not in used
    ][:2]
    recent = [
        number
        for number in pool["recent_active"]
        if number not in used and number not in result
    ]
    result.extend(recent[:2])
    hot = [
        number
        for number in pool["hot"]
        if number not in used and number not in result
    ]
    result.extend(hot[: _PICK_COUNT - len(result)])
    if len(result) < _PICK_COUNT:
        remaining = [
            number
            for number in pool["all"]
            if number not in result
        ]
        result.extend(
            rng.sample(remaining, _PICK_COUNT - len(result))
        )
    return result[:_PICK_COUNT]


def _smart_zone_coverage(
    rng: random.Random,
    pool: dict[str, list[int]],
    used: set[int],
) -> list[int]:
    zones = (
        range(1, 11),
        range(11, 21),
        range(21, 31),
        range(31, 41),
        range(41, 50),
    )
    result: list[int] = []
    for zone in zones:
        candidates = [
            number
            for number in zone
            if number not in used and number not in result
        ]
        hot_in_zone = [
            number for number in candidates if number in pool["hot"]
        ]
        if hot_in_zone:
            result.append(rng.choice(hot_in_zone))
        elif candidates:
            result.append(rng.choice(candidates))
    if len(result) < _PICK_COUNT:
        hot = [
            number
            for number in pool["hot"]
            if number not in result
        ]
        result.extend(
            _sample_up_to(rng, hot, _PICK_COUNT - len(result))
        )
    return result[:_PICK_COUNT]


def _combo_score(numbers: list[int]) -> float:
    score = 0.0
    odd_count = sum(1 for number in numbers if number % 2 == 1)
    if odd_count in (3, 4):
        score += 20
    total = sum(numbers)
    if 128 <= total <= 173:
        score += 20
    elif 100 <= total <= 200:
        score += 10
    zones = ((1, 10), (11, 20), (21, 30), (31, 40), (41, 49))
    score += (
        sum(
            1
            for low, high in zones
            if any(low <= number <= high for number in numbers)
        )
        * 5
    )
    return score


def _smart_constrained(
    rng: random.Random,
    pool: dict[str, list[int]],
    used: set[int],
) -> list[int]:
    del used
    best_combo: list[int] | None = None
    best_score = -1.0
    for _ in range(200):
        candidates: list[int] = []
        candidates.extend(
            _sample_up_to(rng, pool["hot"], 3)
        )
        candidates.extend(
            _sample_up_to(rng, pool["mid"], 2)
        )
        candidates.extend(
            _sample_up_to(rng, pool["comeback"], 2)
        )
        candidates = list(set(candidates))
        if len(candidates) < _PICK_COUNT:
            remaining = [
                number
                for number in pool["all"]
                if number not in candidates
            ]
            candidates.extend(
                rng.sample(
                    remaining,
                    _PICK_COUNT - len(candidates),
                )
            )
        combo = rng.sample(candidates, _PICK_COUNT)
        score = _combo_score(combo)
        if score > best_score:
            best_score = score
            best_combo = combo
    if best_combo is not None:
        return best_combo
    return rng.sample(pool["all"], _PICK_COUNT)


def _smart_multi_bet(
    rng: random.Random,
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[tuple[Ticket, ...], tuple[int, ...]]:
    pool = _build_smart_multi_pool(history)
    used: set[int] = set()
    strategies = (
        _smart_hot_dominant,
        _smart_balanced,
        _smart_cold_comeback,
        _smart_consecutive,
        _smart_zone_coverage,
        _smart_constrained,
    )
    tickets: list[Ticket] = []
    for strategy in strategies:
        ticket = _ticket(strategy(rng, pool, used))
        tickets.append(ticket)
        used.update(ticket)
    pool_counts = tuple(
        len(pool[key])
        for key in (
            "hot",
            "cold",
            "mid",
            "recent_active",
            "last_draw",
            "comeback",
        )
    )
    return tuple(tickets), pool_counts


def generate_legacy_source_native_wave17_portfolio(
    request: LegacySourceNativeWave17Request,
) -> LegacySourceNativeWave17Result:
    """Reproduce the two frozen random-backed source portfolios."""

    _validate_request(request)
    seed_material, seed_digest, seed_integer = _seed(request)
    rng = random.Random()
    rng.seed(seed_integer, version=2)
    if request.legacy_method_id == SCIENTIFIC_SMART_RANDOM_METHOD_ID:
        tickets = _scientific_smart_random(rng)
        candidate_counts: tuple[int, ...] = ()
        runtime_parameters = (
            "lottery_type=BIG_LOTTO",
            "count=7",
            "attempt_limit=1000",
            "causal_history_not_consumed_by_frozen_source",
        )
        native_order = "EV_SCORE_DESCENDING_STABLE_SOURCE_ORDER"
    else:
        tickets, candidate_counts = _smart_multi_bet(
            rng,
            request.history,
        )
        runtime_parameters = (
            "num_bets=6",
            "history_limit=300",
        )
        native_order = "SOURCE_STRATEGY_DECLARATION_ORDER"
    expected_ticket_count = (
        7
        if request.legacy_method_id
        == SCIENTIFIC_SMART_RANDOM_METHOD_ID
        else 6
    )
    if len(tickets) != expected_ticket_count:
        raise LegacySourceNativeWave17SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    history_first = (
        request.history[0].draw_number if request.history else ""
    )
    history_cutoff = (
        request.history[-1].draw_number if request.history else ""
    )
    return LegacySourceNativeWave17Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave17Metadata(
            protocol=SOURCE_NATIVE_WAVE17_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE17_METHOD[
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
                RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE17_METHOD[
                    request.legacy_method_id
                ]
            ),
            randomness_used=True,
            randomness_reproduction=(
                "OUTCOME_BLIND_TARGET_STABLE_CPYTHON_MT19937_SEED"
            ),
            history_draw_count=len(request.history),
            history_first_draw_number=history_first,
            history_cutoff_draw_number=history_cutoff,
            source_history_order=(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE17_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE17_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_order=native_order,
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            source_combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE17_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_candidate_ticket_counts=candidate_counts,
            source_candidate_k_values=(),
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE17_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_runtime_parameters=runtime_parameters,
            candidate_k=None,
            combination_count=None,
        ),
    )


__all__ = [
    "DEFAULT_SOURCE_NATIVE_WAVE17_USER_SEED",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE17_METHOD",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE17_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE17_METHOD",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE17_METHOD",
    "SCIENTIFIC_SMART_RANDOM_METHOD_ID",
    "SMART_MULTI_BET_METHOD_ID",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE17_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE17_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE17_METHOD",
    "SOURCE_NATIVE_WAVE17_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE17_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE17_METHODS",
    "LegacySourceNativeWave17Error",
    "LegacySourceNativeWave17Metadata",
    "LegacySourceNativeWave17Request",
    "LegacySourceNativeWave17Result",
    "LegacySourceNativeWave17SourceError",
    "generate_legacy_source_native_wave17_portfolio",
]
