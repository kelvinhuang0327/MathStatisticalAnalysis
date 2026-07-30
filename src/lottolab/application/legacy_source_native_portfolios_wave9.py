"""Faithful ports of the ninth frozen BIG_LOTTO source-native batch."""

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
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE9_PROTOCOL = "legacy_source_native_wave9/v1"
DEFAULT_SOURCE_NATIVE_WAVE9_USER_SEED = (
    "biglotto-full-universe-source-native-wave9-v1"
)
CLUSTER_PIVOT_BENCHMARK_METHOD_ID = (
    "tools/backtest_cluster_pivot_biglotto.py"
)
TRUE_ORTHOGONAL_METHOD_ID = "tools/research_true_orthogonal.py"
P0P1_UPGRADE_METHOD_ID = "tools/backtest_p0p1_upgrade.py"
SUPPORTED_SOURCE_NATIVE_WAVE9_METHODS = (
    CLUSTER_PIVOT_BENCHMARK_METHOD_ID,
    TRUE_ORTHOGONAL_METHOD_ID,
    P0P1_UPGRADE_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD: Final = {
    CLUSTER_PIVOT_BENCHMARK_METHOD_ID: (
        "b28957a6433e2e42ed7307e524a41be1e04871b2c14a52fd36d15124c4cb02d3"
    ),
    TRUE_ORTHOGONAL_METHOD_ID: (
        "d8652a872a496559c398a8606a2e5965f498f93b4c3c3fef55afe94a5054c3aa"
    ),
    P0P1_UPGRADE_METHOD_ID: (
        "15e895017d2f59e531bd369e8a7975fd4f15418f9294143a38d1fc8c4cb1a0a7"
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE9_METHOD: Final = {
    CLUSTER_PIVOT_BENCHMARK_METHOD_ID: 50,
    TRUE_ORTHOGONAL_METHOD_ID: 100,
    P0P1_UPGRADE_METHOD_ID: 1,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE9_METHOD: Final = {
    CLUSTER_PIVOT_BENCHMARK_METHOD_ID: (
        "7_SOURCE_CONFIGURATIONS_FLATTENED_IN_DECLARATION_AND_BET_ORDER"
    ),
    TRUE_ORTHOGONAL_METHOD_ID: (
        "9_SOURCE_CONFIGURATIONS_FLATTENED_IN_DECLARATION_AND_BET_ORDER"
    ),
    P0P1_UPGRADE_METHOD_ID: (
        "4_SOURCE_CONFIGURATIONS_AT_DEFAULT_SEED_42_FLATTENED_TO_10_POSITIONS"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE9_METHOD: Final = {
    CLUSTER_PIVOT_BENCHMARK_METHOD_ID: "NONE_DETERMINISTIC",
    TRUE_ORTHOGONAL_METHOD_ID: "NONE_DETERMINISTIC",
    P0P1_UPGRADE_METHOD_ID: (
        "random.Random(MT19937)_FROZEN_SEED_42_PLUS_HISTORY_LENGTH"
    ),
}
CANDIDATE_K_BY_SOURCE_NATIVE_WAVE9_METHOD: Final = {
    method_id: None for method_id in SUPPORTED_SOURCE_NATIVE_WAVE9_METHODS
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE9_METHOD: Final = {
    CLUSTER_PIVOT_BENCHMARK_METHOD_ID: 7,
    TRUE_ORTHOGONAL_METHOD_ID: 9,
    P0P1_UPGRADE_METHOD_ID: 4,
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE9_METHOD: Final = {
    CLUSTER_PIVOT_BENCHMARK_METHOD_ID: (
        "single_cluster_pivot",
        "cluster_pivot_2bet",
        "cluster_pivot_3bet",
        "cluster_pivot_4bet",
        "cluster_pivot_window50_2bet",
        "cluster_pivot_hybrid_3bet",
        "cluster_pivot_hybrid_4bet",
    ),
    TRUE_ORTHOGONAL_METHOD_ID: (
        "single_cluster_pivot",
        "single_pure_frequency",
        "single_pure_gap",
        "single_zone_balance",
        "true_orthogonal_2bet",
        "true_orthogonal_3bet",
        "true_orthogonal_4bet",
        "cluster_pivot_multi_window_4bet",
        "diversity_enforced_4bet",
    ),
    P0P1_UPGRADE_METHOD_ID: (
        "deviation_complement_2bet_original",
        "deviation_complement_2bet_p0",
        "mixed_3bet_original_seed42",
        "mixed_3bet_p0p1_seed42",
    ),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE9_METHOD: Final = {
    method_id: "OLDEST_FIRST"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE9_METHODS
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6


class LegacySourceNativeWave9Error(ValueError):
    """A request cannot satisfy the ninth source-native batch contract."""


class LegacySourceNativeWave9SourceError(
    LegacySourceNativeWave9Error
):
    """A frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave9Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE9_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave9Metadata:
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
    source_sample_attempt_counts: tuple[int, ...]
    source_runtime_parameters: tuple[str, ...]
    candidate_k: None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave9Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave9Metadata


@dataclass(frozen=True, slots=True)
class _RawPortfolio:
    tickets: tuple[list[int], ...]
    source_candidate_ticket_counts: tuple[int, ...]
    source_candidate_k_values: tuple[int, ...] = ()
    source_sample_attempt_counts: tuple[int, ...] = ()
    source_runtime_parameters: tuple[str, ...] = ()


def _validate_request(request: LegacySourceNativeWave9Request) -> None:
    if (
        request.legacy_method_id
        not in SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD
    ):
        raise LegacySourceNativeWave9Error(
            "legacy method is outside the ninth source-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacySourceNativeWave9Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacySourceNativeWave9Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacySourceNativeWave9Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacySourceNativeWave9Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(draw.numbers)


def _seed(
    request: LegacySourceNativeWave9Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE9_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD[
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
        raise LegacySourceNativeWave9SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _numbers(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[tuple[int, ...], ...]:
    return tuple(draw.numbers for draw in history)


def _cooccurrence(
    history: tuple[tuple[int, ...], ...],
) -> Counter[tuple[int, int]]:
    result: Counter[tuple[int, int]] = Counter()
    for draw in history:
        for pair in combinations(sorted(draw), 2):
            result[pair] += 1
    return result


def _centers(
    cooccur: Counter[tuple[int, int]],
    top_k: int,
) -> list[int]:
    scores: Counter[int] = Counter()
    for (left, right), count in cooccur.items():
        scores[left] += count
        scores[right] += count
    return [number for number, _count in scores.most_common(top_k)]


def _expand(
    anchor: int,
    cooccur: Counter[tuple[int, int]],
    *,
    exclude: set[int] | None = None,
) -> list[int]:
    excluded: set[int] = set() if exclude is None else exclude
    candidates: Counter[int] = Counter()
    for (left, right), count in cooccur.items():
        if left == anchor and right not in excluded:
            candidates[right] += count
        elif right == anchor and left not in excluded:
            candidates[left] += count
    selected = [anchor]
    for number, _count in candidates.most_common(5):
        if number not in selected:
            selected.append(number)
        if len(selected) >= 6:
            break
    while len(selected) < 6:
        for number in range(1, 50):
            if number not in selected and number not in excluded:
                selected.append(number)
                break
    return sorted(selected[:6])


def _cluster_single(
    history: tuple[tuple[int, ...], ...],
    *,
    window: int | None = None,
) -> list[int]:
    recent = (
        history[-window:]
        if window is not None and len(history) >= window
        else history
    )
    cooccur = _cooccurrence(recent)
    centers = _centers(cooccur, 3)
    return _expand(centers[0], cooccur) if centers else []


def _cluster_multi(
    history: tuple[tuple[int, ...], ...],
    count: int,
    *,
    window: int | None = None,
    exclude_prefix: int,
) -> list[list[int]]:
    recent = (
        history[-window:]
        if window is not None and len(history) >= window
        else history
    )
    cooccur = _cooccurrence(recent)
    centers = _centers(
        cooccur,
        count + 3 if window is not None else {2: 5, 3: 6, 4: 8}[count],
    )
    if len(centers) < count:
        return []
    bets: list[list[int]] = []
    used: set[int] = set()
    for index in range(count):
        bet = _expand(centers[index], cooccur, exclude=used)
        bets.append(bet)
        used.update(bet[:exclude_prefix])
    return bets


def _cluster_three(
    history: tuple[tuple[int, ...], ...],
) -> list[list[int]]:
    cooccur = _cooccurrence(history)
    centers = _centers(cooccur, 6)
    if len(centers) < 3:
        return []
    bet1 = _expand(centers[0], cooccur)
    bet2 = _expand(
        centers[1],
        cooccur,
        exclude=set(bet1[:2]),
    )
    bet3 = _expand(
        centers[2],
        cooccur,
        exclude=set(bet1[:1] + bet2[:1]),
    )
    return [bet1, bet2, bet3]


def _cluster_hybrid(
    history: tuple[tuple[int, ...], ...],
    count: int,
) -> list[list[int]]:
    all_cooccur = _cooccurrence(history)
    centers_all = _centers(all_cooccur, 3)
    cooccur_50 = _cooccurrence(history[-50:])
    centers_50 = _centers(cooccur_50, 3)
    bets: list[list[int]] = []
    used: set[int] = set()
    if centers_all:
        bet = _expand(centers_all[0], all_cooccur)
        bets.append(bet)
        used.update(bet[:2])
    if centers_50 and count >= 2:
        bet = _expand(centers_50[0], cooccur_50, exclude=used)
        bets.append(bet)
        used.update(bet[:2])
    if count >= 3 and len(history) >= 100:
        cooccur_100 = _cooccurrence(history[-100:])
        centers_100 = _centers(cooccur_100, 3)
        if centers_100:
            bet = _expand(
                centers_100[0], cooccur_100, exclude=used
            )
            bets.append(bet)
            used.update(bet[:2])
    if count >= 4 and len(history) >= 30:
        cooccur_30 = _cooccurrence(history[-30:])
        centers_30 = _centers(cooccur_30, 3)
        if centers_30:
            bets.append(
                _expand(centers_30[0], cooccur_30, exclude=used)
            )
    return bets


def _cluster_benchmark(
    history: tuple[tuple[int, ...], ...],
) -> _RawPortfolio:
    configurations = (
        [_cluster_single(history)],
        _cluster_multi(history, 2, exclude_prefix=2),
        _cluster_three(history),
        _cluster_multi(history, 4, exclude_prefix=1),
        _cluster_multi(
            history, 2, window=50, exclude_prefix=2
        ),
        _cluster_hybrid(history, 3),
        _cluster_hybrid(history, 4),
    )
    return _RawPortfolio(
        tickets=tuple(
            ticket
            for configuration in configurations
            for ticket in configuration
            if ticket
        ),
        source_candidate_ticket_counts=tuple(
            len(configuration) for configuration in configurations
        ),
    )


def _pure_frequency(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    frequency: Counter[int] = Counter(
        number for draw in history[-50:] for number in draw
    )
    return sorted(
        number for number, _count in frequency.most_common(6)
    )


def _pure_gap(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    gaps: dict[int, int] = {}
    for number in range(1, 50):
        gaps[number] = len(history)
        for index, draw in enumerate(reversed(history)):
            if number in draw:
                gaps[number] = index
                break
    return sorted(
        sorted(gaps, key=lambda number: -gaps[number])[:6]
    )


def _zone_balance(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    zones = (
        range(1, 10),
        range(10, 20),
        range(20, 30),
        range(30, 40),
        range(40, 50),
    )
    frequency: Counter[int] = Counter(
        number for draw in history[-100:] for number in draw
    )
    selected: list[int] = []
    for zone in zones:
        zone_numbers = sorted(
            zone, key=lambda number: -frequency.get(number, 0)
        )
        for number in zone_numbers[:2]:
            if len(selected) < 6:
                selected.append(number)
    return sorted(selected[:6])


def _odd_even(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    frequency: Counter[int] = Counter(
        number for draw in history[-100:] for number in draw
    )
    odds = sorted(
        range(1, 50, 2),
        key=lambda number: -frequency.get(number, 0),
    )
    evens = sorted(
        range(2, 50, 2),
        key=lambda number: -frequency.get(number, 0),
    )
    return sorted((odds[:3] + evens[:3])[:6])


def _true_orthogonal(
    history: tuple[tuple[int, ...], ...],
) -> _RawPortfolio:
    cluster = _cluster_single(history)
    frequency = _pure_frequency(history)
    gap = _pure_gap(history)
    zone = _zone_balance(history)
    odd_even = _odd_even(history)
    orthogonal_2 = [cluster, gap] if cluster and gap else []
    orthogonal_3 = [
        ticket
        for ticket in (cluster, frequency, zone)
        if ticket
    ]
    orthogonal_4 = [
        ticket
        for ticket in (cluster, gap, zone, odd_even)
        if ticket
    ]
    multiwindow: list[list[int]] = []
    seen: set[tuple[int, ...]] = set()
    for window in (50, 100, 200, None):
        bet = _cluster_single(history, window=window)
        key = tuple(bet)
        if bet and key not in seen:
            multiwindow.append(bet)
            seen.add(key)
    multiwindow = multiwindow[:4]
    diversity: list[list[int]] = []
    all_used: set[int] = set()
    for bet in (cluster, frequency, gap, zone, odd_even):
        if len(diversity) >= 4:
            break
        if bet and len(set(bet) & all_used) <= 2:
            diversity.append(bet)
            all_used.update(bet)
    configurations = (
        [cluster],
        [frequency],
        [gap],
        [zone],
        orthogonal_2,
        orthogonal_3,
        orthogonal_4,
        multiwindow,
        diversity,
    )
    return _RawPortfolio(
        tickets=tuple(
            ticket
            for configuration in configurations
            for ticket in configuration
            if ticket
        ),
        source_candidate_ticket_counts=tuple(
            len(configuration) for configuration in configurations
        ),
    )


def _base_hot_cold(
    history: tuple[tuple[int, ...], ...],
    *,
    echo_boost: float | None,
) -> tuple[list[int], list[int], set[int], dict[int, float], float]:
    recent = history[-50:] if len(history) > 50 else history
    expected = len(recent) * 6 / 49
    frequency: Counter[int] = Counter(
        number for draw in recent for number in draw
    )
    scores = {
        number: frequency.get(number, 0) - expected
        for number in range(1, 50)
    }
    if echo_boost is not None and len(history) >= 3:
        for number in set(history[-2]):
            scores[number] += echo_boost
    hot: list[tuple[int, float]] = []
    cold: list[tuple[int, float]] = []
    for number in range(1, 50):
        score = scores[number]
        if score > 1:
            hot.append((number, score))
        elif score < -1:
            cold.append((number, abs(score)))
    hot.sort(key=lambda item: item[1], reverse=True)
    cold.sort(key=lambda item: item[1], reverse=True)
    bet1 = [number for number, _score in hot[:6]]
    used = set(bet1)
    if len(bet1) < 6:
        middle = sorted(
            range(1, 50), key=lambda number: abs(scores[number])
        )
        for number in middle:
            if number not in used and len(bet1) < 6:
                bet1.append(number)
                used.add(number)
    bet2: list[int] = []
    for number, _score in cold:
        if number not in used and len(bet2) < 6:
            bet2.append(number)
            used.add(number)
    if len(bet2) < 6:
        for number in range(1, 50):
            if number not in used and len(bet2) < 6:
                bet2.append(number)
                used.add(number)
    return sorted(bet1[:6]), sorted(bet2[:6]), used, scores, expected


def _structural_score(bet: list[int]) -> int:
    total = sum(bet)
    odd = sum(1 for number in bet if number % 2 == 1)
    zones = [0, 0, 0]
    for number in bet:
        if number <= 16:
            zones[0] += 1
        elif number <= 33:
            zones[1] += 1
        else:
            zones[2] += 1
    consecutive = sum(
        1
        for index in range(len(bet) - 1)
        if bet[index + 1] - bet[index] == 1
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


def _mixed_original(
    history: tuple[tuple[int, ...], ...],
    *,
    seed: int,
) -> tuple[list[list[int]], int]:
    bet1, bet2, used, _scores, _expected = _base_hot_cold(
        history, echo_boost=None
    )
    frequency: Counter[int] = Counter(
        number for draw in history[-100:] for number in draw
    )
    ranked = sorted(
        range(1, 50),
        key=lambda number: frequency.get(number, 0),
        reverse=True,
    )
    available = [number for number in ranked if number not in used][
        :24
    ]
    if len(available) < 6:
        available = [
            number for number in range(1, 50) if number not in used
        ]
    rng = random.Random(seed + len(history))
    best_bet: list[int] | None = None
    best_score = -1
    for _attempt in range(200):
        if len(available) < 6:
            break
        bet = sorted(rng.sample(available, 6))
        score = _structural_score(bet)
        if score > best_score:
            best_score = score
            best_bet = bet
    if best_bet is None:
        best_bet = sorted(available[:6])
    return [bet1, bet2, best_bet], len(available)


def _mixed_p0p1(
    history: tuple[tuple[int, ...], ...],
    *,
    seed: int,
) -> tuple[list[list[int]], int]:
    bet1, bet2, used, _scores, expected = _base_hot_cold(
        history, echo_boost=1.5
    )
    recent = history[-50:] if len(history) > 50 else history
    raw_frequency: Counter[int] = Counter(
        number for draw in recent for number in draw
    )
    gray_zone: list[tuple[int, int, float]] = []
    for number in range(1, 50):
        if number in used:
            continue
        raw_deviation = raw_frequency.get(number, 0) - expected
        if -1.5 <= raw_deviation <= 1.5:
            gap = 0
            for index in range(len(history) - 1, -1, -1):
                if number in history[index]:
                    gap = len(history) - 1 - index
                    break
                gap = len(history) - index
            gray_zone.append((number, gap, raw_deviation))
    gray_zone.sort(key=lambda item: item[1], reverse=True)
    available = [number for number, _gap, _dev in gray_zone]
    if len(available) < 6:
        for number in range(1, 50):
            if number not in used and number not in available:
                available.append(number)
    pool_size = min(len(available), max(12, len(available) // 2))
    sample_pool = available[:pool_size]
    if len(sample_pool) < 6:
        sample_pool = available
    rng = random.Random(seed + len(history))
    best_bet: list[int] | None = None
    best_score = -1
    for _attempt in range(200):
        if len(available) < 6:
            break
        bet = sorted(rng.sample(sample_pool, 6))
        score = _structural_score(bet)
        if score > best_score:
            best_score = score
            best_bet = bet
    if best_bet is None:
        best_bet = sorted(available[:6])
    return [bet1, bet2, best_bet], len(sample_pool)


def _p0p1_upgrade(
    history: tuple[tuple[int, ...], ...],
) -> _RawPortfolio:
    original_2 = list(
        _base_hot_cold(history, echo_boost=None)[:2]
    )
    p0_2 = list(
        _base_hot_cold(history, echo_boost=1.5)[:2]
    )
    original_3, original_k = _mixed_original(history, seed=42)
    p0p1_3, p0p1_k = _mixed_p0p1(history, seed=42)
    configurations = (original_2, p0_2, original_3, p0p1_3)
    return _RawPortfolio(
        tickets=tuple(
            ticket
            for configuration in configurations
            for ticket in configuration
        ),
        source_candidate_ticket_counts=(2, 2, 3, 3),
        source_candidate_k_values=(original_k, p0p1_k),
        source_sample_attempt_counts=(200, 200),
        source_runtime_parameters=(
            "default_seed=42",
            f"effective_rng_seed={42 + len(history)}",
            "echo_boost=1.5",
        ),
    )


def _raw_portfolio(
    request: LegacySourceNativeWave9Request,
) -> _RawPortfolio:
    history = _numbers(request.history)
    if request.legacy_method_id == CLUSTER_PIVOT_BENCHMARK_METHOD_ID:
        return _cluster_benchmark(history)
    if request.legacy_method_id == TRUE_ORTHOGONAL_METHOD_ID:
        return _true_orthogonal(history)
    return _p0p1_upgrade(history)


def generate_legacy_source_native_wave9_portfolio(
    request: LegacySourceNativeWave9Request,
) -> LegacySourceNativeWave9Result:
    """Generate source-ordered native tickets from strictly prior history."""

    _validate_request(request)
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE9_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave9Error(
            f"method requires at least {minimum} history draws"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    raw = _raw_portfolio(request)
    if not raw.tickets:
        raise LegacySourceNativeWave9SourceError(
            "FROZEN_SOURCE_NO_NATIVE_TICKETS"
        )
    tickets = tuple(_ticket(ticket) for ticket in raw.tickets)
    random_protocol = RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE9_METHOD[
        request.legacy_method_id
    ]
    return LegacySourceNativeWave9Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave9Metadata(
            protocol=SOURCE_NATIVE_WAVE9_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD[
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
            source_history_order="OLDEST_FIRST",
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE9_METHOD[
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
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE9_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_candidate_ticket_counts=(
                raw.source_candidate_ticket_counts
            ),
            source_candidate_k_values=raw.source_candidate_k_values,
            source_sample_attempt_counts=(
                raw.source_sample_attempt_counts
            ),
            source_runtime_parameters=raw.source_runtime_parameters,
            candidate_k=None,
            combination_count=None,
        ),
    )


__all__ = [
    "CANDIDATE_K_BY_SOURCE_NATIVE_WAVE9_METHOD",
    "CLUSTER_PIVOT_BENCHMARK_METHOD_ID",
    "DEFAULT_SOURCE_NATIVE_WAVE9_USER_SEED",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE9_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE9_METHOD",
    "P0P1_UPGRADE_METHOD_ID",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE9_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE9_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE9_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE9_METHOD",
    "SOURCE_NATIVE_WAVE9_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE9_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE9_METHODS",
    "TRUE_ORTHOGONAL_METHOD_ID",
    "LegacySourceNativeWave9Error",
    "LegacySourceNativeWave9Metadata",
    "LegacySourceNativeWave9Request",
    "LegacySourceNativeWave9Result",
    "LegacySourceNativeWave9SourceError",
    "generate_legacy_source_native_wave9_portfolio",
]
