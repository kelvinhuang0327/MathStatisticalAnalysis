"""DB-free target-native port of the frozen BIG_LOTTO Smart Multi-Bet donor.

The donor is ``lottery_api/models/smart_multi_bet.py`` at legacy commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` (blob
``910ccf647b6ec0a2969f9c6ee21ad3c7c2796435``, SHA-256
``613c62c1f1929903e5d58309fccd9a7fd7c755be15d188cf9ab01ffe43f092e9``).
Its ``SmartMultiBetSystem`` behavior is retained by the Wave-17 source-native
oracle, whose frozen-class checks establish exact output parity.

The donor shell reads the newest 300 BIG_LOTTO rows from SQLite and then calls
the pure prediction class. This adapter removes only that shell: callers supply
oldest-first immutable causal history, which is bounded to the same latest 300
rows and reversed at the prediction edge. The donor's six declared portfolio
branches, shared used-number set, sampling order, 200 constrained retries,
fallbacks, and positional ticket order remain unchanged. Its unpreserved
module-global random state is replaced by the established Wave-17 isolated
``random.Random`` seed protocol. No database, persistence, scheduler,
performance history, or learned state is imported or consulted.
"""

from __future__ import annotations

import hashlib
import random
from collections import Counter

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InvalidOutput,
    PortfolioBetAdapter,
)

_STRATEGY_ID = "legacy_biglotto__smart_multi_bet__613c62c1f192"
_SOURCE_NATIVE_WAVE17_PROTOCOL = "legacy_source_native_wave17/v1"
_SOURCE_METHOD_ID = "lottery_api/models/smart_multi_bet.py"
_SOURCE_SHA256 = "613c62c1f1929903e5d58309fccd9a7fd7c755be15d188cf9ab01ffe43f092e9"
_DEFAULT_USER_SEED = "biglotto-full-universe-source-native-wave17-v1"
_REPLICATE_ID = 0
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_HISTORY_LIMIT = 300
_NATIVE_TICKET_COUNT = 6


def _ticket(numbers: list[int]) -> tuple[int, ...]:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(
            type(number) is not int or not _MIN_NUMBER <= number <= _MAX_NUMBER for number in values
        )
    ):
        raise InvalidOutput(f"{_STRATEGY_ID}: Smart Multi-Bet ticket is not a legal 6-of-49 set")
    return values


def _target_after_causal_cutoff(history: tuple[CausalDrawRow, ...]) -> str:
    """Derive a stable next-target identity without observing a future draw."""

    draw_ids = {row.draw for row in history}
    target = f"{history[-1].draw}:lottolab-smart-multi-bet-next-target"
    while target in draw_ids:
        target = f"{target}:next"
    return target


def _seed_integer(
    *,
    target_draw_number: str,
    user_seed: str | int = _DEFAULT_USER_SEED,
) -> int:
    material = "|".join(
        (
            _SOURCE_NATIVE_WAVE17_PROTOCOL,
            _SOURCE_METHOD_ID,
            _SOURCE_SHA256,
            target_draw_number,
            str(_REPLICATE_ID),
            str(user_seed),
        )
    )
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest(), 16)


def _build_candidate_pool(
    history: tuple[CausalDrawRow, ...],
) -> dict[str, list[int]]:
    recent_first = tuple(reversed(history[-_HISTORY_LIMIT:]))
    frequency: Counter[int] = Counter()
    for draw in recent_first[:50]:
        frequency.update(draw.numbers)
    recent_frequency: Counter[int] = Counter()
    for draw in recent_first[:20]:
        recent_frequency.update(draw.numbers)

    all_numbers = list(range(_MIN_NUMBER, _MAX_NUMBER + 1))
    hot_numbers = [number for number, _count in frequency.most_common(15)]
    cold_numbers = [number for number, _count in frequency.most_common()[-15:]]
    mid_numbers = [
        number for number in all_numbers if number not in hot_numbers and number not in cold_numbers
    ]
    recent_active = [number for number, count in recent_frequency.items() if count >= 2]
    last_numbers = list(recent_first[0].numbers) if recent_first else []

    comeback: list[tuple[int, float]] = []
    for number in all_numbers:
        current_gap = len(recent_first)
        for index, draw in enumerate(recent_first):
            if number in draw.numbers:
                current_gap = index
                break
        appearances = [index for index, draw in enumerate(recent_first) if number in draw.numbers]
        if len(appearances) < 3:
            continue
        gaps = [
            appearances[index + 1] - appearances[index] for index in range(len(appearances) - 1)
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


def _hot_dominant(
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
        number for number in pool["mid"] if number not in used and number not in result
    ]
    result.extend(_sample_up_to(rng, mid_candidates, _PICK_COUNT - len(result)))
    if len(result) < _PICK_COUNT:
        remaining = [number for number in pool["all"] if number not in result]
        result.extend(rng.sample(remaining, _PICK_COUNT - len(result)))
    return result[:_PICK_COUNT]


def _balanced(
    rng: random.Random,
    pool: dict[str, list[int]],
    used: set[int],
) -> list[int]:
    result: list[int] = []
    for category, count in (("hot", 2), ("mid", 2), ("cold", 2)):
        candidates = [
            number for number in pool[category] if number not in used and number not in result
        ]
        result.extend(_sample_up_to(rng, candidates, count))
    if len(result) < _PICK_COUNT:
        remaining = [number for number in pool["all"] if number not in result]
        result.extend(rng.sample(remaining, _PICK_COUNT - len(result)))
    return result[:_PICK_COUNT]


def _cold_comeback(
    rng: random.Random,
    pool: dict[str, list[int]],
    used: set[int],
) -> list[int]:
    result = [number for number in pool["comeback"] if number not in used][:4]
    hot = [number for number in pool["hot"] if number not in used and number not in result]
    result.extend(hot[: _PICK_COUNT - len(result)])
    if len(result) < _PICK_COUNT:
        remaining = [number for number in pool["all"] if number not in result]
        result.extend(rng.sample(remaining, _PICK_COUNT - len(result)))
    return result[:_PICK_COUNT]


def _consecutive(
    rng: random.Random,
    pool: dict[str, list[int]],
    used: set[int],
) -> list[int]:
    result = [number for number in pool["last_draw"] if number not in used][:2]
    recent = [
        number for number in pool["recent_active"] if number not in used and number not in result
    ]
    result.extend(recent[:2])
    hot = [number for number in pool["hot"] if number not in used and number not in result]
    result.extend(hot[: _PICK_COUNT - len(result)])
    if len(result) < _PICK_COUNT:
        remaining = [number for number in pool["all"] if number not in result]
        result.extend(rng.sample(remaining, _PICK_COUNT - len(result)))
    return result[:_PICK_COUNT]


def _zone_coverage(
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
        candidates = [number for number in zone if number not in used and number not in result]
        hot_in_zone = [number for number in candidates if number in pool["hot"]]
        if hot_in_zone:
            result.append(rng.choice(hot_in_zone))
        elif candidates:
            result.append(rng.choice(candidates))
    if len(result) < _PICK_COUNT:
        hot = [number for number in pool["hot"] if number not in result]
        result.extend(_sample_up_to(rng, hot, _PICK_COUNT - len(result)))
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
    score += sum(1 for low, high in zones if any(low <= number <= high for number in numbers)) * 5
    return score


def _constrained(
    rng: random.Random,
    pool: dict[str, list[int]],
    used: set[int],
) -> list[int]:
    del used
    best_combo: list[int] | None = None
    best_score = -1.0
    for _ in range(200):
        candidates: list[int] = []
        candidates.extend(_sample_up_to(rng, pool["hot"], 3))
        candidates.extend(_sample_up_to(rng, pool["mid"], 2))
        candidates.extend(_sample_up_to(rng, pool["comeback"], 2))
        candidates = list(set(candidates))
        if len(candidates) < _PICK_COUNT:
            remaining = [number for number in pool["all"] if number not in candidates]
            candidates.extend(rng.sample(remaining, _PICK_COUNT - len(candidates)))
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
    history: tuple[CausalDrawRow, ...],
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]]:
    pool = _build_candidate_pool(history)
    used: set[int] = set()
    strategies = (
        _hot_dominant,
        _balanced,
        _cold_comeback,
        _consecutive,
        _zone_coverage,
        _constrained,
    )
    tickets: list[tuple[int, ...]] = []
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


class BigLottoSmartMultiBetAdapter(PortfolioBetAdapter):
    """Seeded, exact-cardinality six-ticket Smart Multi-Bet portfolio."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Smart Multi-Bet 6注"
    strategy_version = "v0.1"
    min_history = 1
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _NATIVE_TICKET_COUNT

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        return history[-_HISTORY_LIMIT:]

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        del lottery_type
        if len({row.draw for row in history}) != len(history):
            raise InvalidOutput(f"{self.strategy_id}: causal draw identities must be unique")
        seed_integer = _seed_integer(target_draw_number=_target_after_causal_cutoff(history))
        rng = random.Random()
        rng.seed(seed_integer, version=2)
        tickets, _pool_counts = _smart_multi_bet(rng, history)
        return tickets


__all__ = ["BigLottoSmartMultiBetAdapter"]
