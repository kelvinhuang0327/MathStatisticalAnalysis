"""Faithful ports of the eighth frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE8_PROTOCOL = "legacy_source_native_wave8/v1"
DEFAULT_SOURCE_NATIVE_WAVE8_USER_SEED = (
    "biglotto-full-universe-source-native-wave8-v1"
)
GEMINI_PHASE2_METHOD_ID = "tools/verify_gemini_phase2_claim.py"
DYNAMIC_FREQUENCY_METHOD_ID = "tools/dynamic_frequency_predictor.py"
CLUSTER_ENHANCEMENTS_METHOD_ID = "tools/research_cluster_enhancements.py"
OPTIMIZE_THIRD_BET_METHOD_ID = "tools/optimize_3rd_bet.py"
SUPPORTED_SOURCE_NATIVE_WAVE8_METHODS = (
    GEMINI_PHASE2_METHOD_ID,
    DYNAMIC_FREQUENCY_METHOD_ID,
    CLUSTER_ENHANCEMENTS_METHOD_ID,
    OPTIMIZE_THIRD_BET_METHOD_ID,
)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE8_METHOD: Final = {
    GEMINI_PHASE2_METHOD_ID: (
        "6407a8f3951913fcd2de6b98046305defd377739e67d7f37b53884f81964b480"
    ),
    DYNAMIC_FREQUENCY_METHOD_ID: (
        "36e5bf9998acd0c3d018e75b761d0f41066da2570458d582486d619cfd1aad69"
    ),
    CLUSTER_ENHANCEMENTS_METHOD_ID: (
        "7b28a78812704b2c8cb0712e5c86dd4ea24568fd4923f107301b5451d71cb093"
    ),
    OPTIMIZE_THIRD_BET_METHOD_ID: (
        "9a1f7010d181cc8561d6a99fb7156e32297b299993f0c6c11db873a6b4800d98"
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE8_METHOD: Final = {
    GEMINI_PHASE2_METHOD_ID: 100,
    DYNAMIC_FREQUENCY_METHOD_ID: 200,
    CLUSTER_ENHANCEMENTS_METHOD_ID: 100,
    OPTIMIZE_THIRD_BET_METHOD_ID: 1,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE8_METHOD: Final = {
    GEMINI_PHASE2_METHOD_ID: (
        "7_METHOD_TICKETS_IN_FROZEN_GENERATE_7_BETS_ORDER"
    ),
    DYNAMIC_FREQUENCY_METHOD_ID: (
        "1_TICKET_FROM_BEST_OF_5_FROZEN_FREQUENCY_WINDOWS"
    ),
    CLUSTER_ENHANCEMENTS_METHOD_ID: (
        "8_SOURCE_CONFIGURATIONS_FLATTENED_IN_DECLARATION_AND_BET_ORDER"
    ),
    OPTIMIZE_THIRD_BET_METHOD_ID: (
        "1_COMPLEMENT_TICKET_FOR_2_FROZEN_PURCHASED_TICKETS"
    ),
}
RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE8_METHOD: Final = {
    method_id: "NONE_DETERMINISTIC"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE8_METHODS
}
CANDIDATE_K_BY_SOURCE_NATIVE_WAVE8_METHOD: Final = {
    GEMINI_PHASE2_METHOD_ID: None,
    DYNAMIC_FREQUENCY_METHOD_ID: None,
    CLUSTER_ENHANCEMENTS_METHOD_ID: None,
    OPTIMIZE_THIRD_BET_METHOD_ID: None,
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE8_METHOD: Final = {
    GEMINI_PHASE2_METHOD_ID: 7,
    DYNAMIC_FREQUENCY_METHOD_ID: 5,
    CLUSTER_ENHANCEMENTS_METHOD_ID: 8,
    OPTIMIZE_THIRD_BET_METHOD_ID: 1,
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE8_METHOD: Final = {
    GEMINI_PHASE2_METHOD_ID: (
        "markov",
        "statistical",
        "deviation",
        "frequency",
        "trend",
        "bayesian",
        "hot_cold_mix",
    ),
    DYNAMIC_FREQUENCY_METHOD_ID: (
        "window=30",
        "window=50",
        "window=100",
        "window=200",
        "window=300",
    ),
    CLUSTER_ENHANCEMENTS_METHOD_ID: (
        "1bet_cluster_pivot",
        "1bet_triplet",
        "1bet_temporal",
        "1bet_gap_compensation",
        "1bet_graph_community",
        "1bet_anti_cooccur",
        "4bet_orthogonal",
        "5bet_hybrid",
    ),
    OPTIMIZE_THIRD_BET_METHOD_ID: (
        "generate_optimal_3rd_bet",
    ),
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE8_METHOD: Final = {
    method_id: "OLDEST_FIRST"
    for method_id in SUPPORTED_SOURCE_NATIVE_WAVE8_METHODS
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_FROZEN_PURCHASED_BET_1 = (1, 18, 23, 40, 43, 46)
_FROZEN_PURCHASED_BET_2 = (16, 21, 22, 31, 40, 48)


class LegacySourceNativeWave8Error(ValueError):
    """A request cannot satisfy the eighth source-native batch contract."""


class LegacySourceNativeWave8SourceError(
    LegacySourceNativeWave8Error
):
    """A frozen source emitted no valid six-number native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave8Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE8_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave8Metadata:
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
    source_runtime_parameters: tuple[str, ...]
    candidate_k: int | None
    candidate_combination_count: int | None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave8Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave8Metadata


@dataclass(frozen=True, slots=True)
class _RawPortfolio:
    tickets: tuple[tuple[int, ...] | list[int], ...]
    source_candidate_ticket_counts: tuple[int, ...] = ()
    source_runtime_parameters: tuple[str, ...] = ()
    candidate_k: int | None = None
    candidate_combination_count: int | None = None


def _validate_request(request: LegacySourceNativeWave8Request) -> None:
    if (
        request.legacy_method_id
        not in SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE8_METHOD
    ):
        raise LegacySourceNativeWave8Error(
            "legacy method is outside the eighth source-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacySourceNativeWave8Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacySourceNativeWave8Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacySourceNativeWave8Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacySourceNativeWave8Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(draw.numbers)


def _seed(
    request: LegacySourceNativeWave8Request,
) -> tuple[str, str, int]:
    source_sha256 = SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE8_METHOD[
        request.legacy_method_id
    ]
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE8_PROTOCOL,
            request.legacy_method_id,
            source_sha256,
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
        raise LegacySourceNativeWave8SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _history_numbers(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[tuple[int, ...], ...]:
    return tuple(draw.numbers for draw in history)


def _frequency_ticket(
    history: tuple[tuple[int, ...], ...],
    window: int,
) -> list[int]:
    recent = history[-window:] if len(history) > window else history
    frequency: Counter[int] = Counter(
        number for draw in recent for number in draw
    )
    return [number for number, _count in frequency.most_common(6)]


def _gemini_markov(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    transitions: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for index in range(len(history) - 1):
        for number in set(history[index]):
            for next_number in set(history[index + 1]):
                transitions[number][next_number] += 1
    scores: Counter[int] = Counter()
    for number in set(history[-1]):
        for next_number, count in transitions[number].items():
            scores[next_number] += count
    selected = [number for number, _count in scores.most_common(6)]
    for number in range(1, 50):
        if number not in selected:
            selected.append(number)
        if len(selected) >= 6:
            break
    return sorted(selected[:6])


def _gemini_statistical(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    frequency: Counter[int] = Counter(
        number for draw in history[-100:] for number in draw
    )
    gap: dict[int, int] = {}
    for number in range(1, 50):
        gap[number] = 0
        for index, draw in enumerate(reversed(history)):
            if number in draw:
                gap[number] = index
                break
    scores: dict[int, float] = {}
    for number in range(1, 50):
        scores[number] = (
            frequency.get(number, 0) * 0.6 + gap.get(number, 0) * 0.4
        )
    return sorted(
        sorted(scores, key=lambda number: scores[number], reverse=True)[:6]
    )


def _gemini_deviation(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    expected = sum(len(draw) for draw in history) / 49
    frequency: Counter[int] = Counter(
        number for draw in history for number in draw
    )
    scores: dict[int, float] = {}
    for number in range(1, 50):
        scores[number] = expected - frequency.get(number, 0)
    return sorted(
        sorted(scores, key=lambda number: scores[number], reverse=True)[:6]
    )


def _gemini_trend(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    recent: Counter[int] = Counter(
        number for draw in history[-20:] for number in draw
    )
    medium: Counter[int] = Counter(
        number for draw in history[-50:-20] for number in draw
    )
    scores: dict[int, float] = {}
    for number in range(1, 50):
        recent_rate = recent.get(number, 0) / 20
        medium_rate = (
            medium.get(number, 0) / 30
            if medium.get(number, 0)
            else 0.01
        )
        scores[number] = recent_rate / max(medium_rate, 0.01)
    return sorted(
        sorted(scores, key=lambda number: scores[number], reverse=True)[:6]
    )


def _gemini_bayesian(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    prior = 1.0 / 49
    frequency: Counter[int] = Counter(
        number for draw in history for number in draw
    )
    total = sum(frequency.values())
    posterior: dict[int, float] = {}
    for number in range(1, 50):
        likelihood = (
            frequency.get(number, 0) / total if total > 0 else prior
        )
        posterior[number] = likelihood * prior
    total_posterior = sum(posterior.values())
    if total_posterior > 0:
        posterior = {
            number: value / total_posterior
            for number, value in posterior.items()
        }
    return sorted(
        sorted(posterior, key=lambda number: -posterior[number])[:6]
    )


def _gemini_hot_cold(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    recent: Counter[int] = Counter(
        number for draw in history[-30:] for number in draw
    )
    hot = [number for number, _count in recent.most_common(4)]
    cold = [
        number for number in range(1, 50) if recent.get(number, 0) == 0
    ]
    if len(cold) < 3:
        cold = [
            number for number, _count in recent.most_common()[-3:]
        ]
    selected = hot[:3] + cold[:3]
    for number in range(1, 50):
        if number not in selected and len(selected) < 6:
            selected.append(number)
    return sorted(selected[:6])


def _gemini_phase2(
    history: tuple[tuple[int, ...], ...],
) -> _RawPortfolio:
    tickets = (
        _gemini_markov(history),
        _gemini_statistical(history),
        sorted(_frequency_ticket(history, 50)),
    )
    ordered = (
        tickets[0],
        tickets[1],
        _gemini_deviation(history),
        tickets[2],
        _gemini_trend(history),
        _gemini_bayesian(history),
        _gemini_hot_cold(history),
    )
    return _RawPortfolio(
        tickets=ordered,
        source_candidate_ticket_counts=(1, 1, 1, 1, 1, 1, 1),
    )


def _dynamic_frequency(
    history: tuple[tuple[int, ...], ...],
) -> _RawPortfolio:
    windows = (30, 50, 100, 200, 300)
    scores: dict[int, float] = {}
    for window in windows:
        total_hits = 0
        for index in range(50):
            target_index = len(history) - 50 + index
            predicted = set(
                _frequency_ticket(history[:target_index], window)
            )
            total_hits += len(predicted & set(history[target_index]))
        scores[window] = total_hits / 50
    best_window = max(windows, key=lambda window: scores[window])
    ticket = sorted(_frequency_ticket(history, best_window))
    return _RawPortfolio(
        tickets=(ticket,),
        source_candidate_ticket_counts=(1, 1, 1, 1, 1),
        source_runtime_parameters=(
            f"best_window={best_window}",
            *(
                f"window_score_{window}={scores[window]:.17g}"
                for window in windows
            ),
        ),
    )


def _cooccurrence(
    history: tuple[tuple[int, ...], ...],
) -> Counter[tuple[int, int]]:
    counts: Counter[tuple[int, int]] = Counter()
    for draw in history:
        for pair in combinations(sorted(draw), 2):
            counts[pair] += 1
    return counts


def _cluster_centers(
    cooccur: Counter[tuple[int, int]],
    *,
    top_k: int,
) -> list[int]:
    scores: Counter[int] = Counter()
    for (left, right), count in cooccur.items():
        scores[left] += count
        scores[right] += count
    return [number for number, _count in scores.most_common(top_k)]


def _expand_anchor(
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


def _cluster_base(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    cooccur = _cooccurrence(history)
    centers = _cluster_centers(cooccur, top_k=3)
    return _expand_anchor(centers[0], cooccur) if centers else []


def _triplet(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    triplets: Counter[tuple[int, int, int]] = Counter()
    for draw in history[-200:]:
        for trio in combinations(sorted(draw), 3):
            triplets[trio] += 1
    top_triplets = triplets.most_common(10)
    if not top_triplets:
        return []
    base_triplet = list(top_triplets[0][0])
    selected = set(base_triplet)
    cooccur = _cooccurrence(history[-200:])
    ordered_pairs = sorted(
        cooccur.items(), key=lambda item: -item[1]
    )
    for anchor in base_triplet:
        if len(selected) >= 6:
            break
        for (left, right), _count in ordered_pairs:
            if left == anchor and right not in selected:
                selected.add(right)
            elif right == anchor and left not in selected:
                selected.add(left)
            if len(selected) >= 6:
                break
    return sorted(list(selected)[:6])


def _temporal(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    scores: Counter[int] = Counter()
    for index in range(len(history) - 1):
        for number in set(history[index]) & set(history[index + 1]):
            scores[number] += 1
    selected = [number for number, _count in scores.most_common(6)]
    if len(selected) < 6:
        frequency: Counter[int] = Counter(
            number for draw in history[-50:] for number in draw
        )
        for number, _count in frequency.most_common():
            if number not in selected:
                selected.append(number)
            if len(selected) >= 6:
                break
    return sorted(selected[:6])


def _gap_compensation(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    gaps: dict[int, int] = {}
    for number in range(1, 50):
        gaps[number] = len(history)
        for index, draw in enumerate(reversed(history)):
            if number in draw:
                gaps[number] = index
                break
    long_gap = [
        number for number in range(1, 50) if gaps[number] > 20
    ]
    if not long_gap:
        long_gap = sorted(gaps, key=lambda number: -gaps[number])[:10]
    cooccur = _cooccurrence(history)
    scores: Counter[int] = Counter()
    for number in long_gap:
        for (left, right), count in cooccur.items():
            if left == number or right == number:
                scores[number] += count
    selected = [number for number, _count in scores.most_common(6)]
    if len(selected) < 6:
        for number in long_gap:
            if number not in selected:
                selected.append(number)
            if len(selected) >= 6:
                break
    return sorted(selected[:6])


def _graph_community(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    cooccur = _cooccurrence(history[-150:])
    adjacency: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for (left, right), count in cooccur.items():
        adjacency[left][right] = count
        adjacency[right][left] = count
    degree = {
        number: sum(adjacency[number].values())
        for number in range(1, 50)
    }
    top_nodes = sorted(degree, key=lambda number: -degree[number])[:10]
    selected = [top_nodes[0]]
    for neighbor, _count in adjacency[top_nodes[0]].most_common(5):
        if neighbor not in selected:
            selected.append(neighbor)
        if len(selected) >= 6:
            break
    return sorted(selected[:6])


def _anti_cooccur(
    history: tuple[tuple[int, ...], ...],
) -> list[int]:
    cooccur = _cooccurrence(history)
    scores: Counter[int] = Counter()
    for (left, right), count in cooccur.items():
        scores[left] += count
        scores[right] += count
    least_common = [
        number for number, _count in scores.most_common()[:-11:-1]
    ]
    return sorted(least_common[:6])


def _orthogonal_four(
    history: tuple[tuple[int, ...], ...],
) -> list[list[int]]:
    bets: list[list[int]] = []
    bet1 = _cluster_base(history)
    if bet1:
        bets.append(bet1)
    bet2 = _triplet(history)
    if bet2 and bet2 != bet1:
        bets.append(bet2)
    bet3 = _gap_compensation(history)
    if bet3:
        bets.append(bet3)
    bet4 = _temporal(history)
    if bet4:
        bets.append(bet4)
    return bets[:4]


def _hybrid_five(
    history: tuple[tuple[int, ...], ...],
) -> list[list[int]]:
    bets: list[list[int]] = []
    for window in (50, 100, 200):
        if len(history) >= window:
            cooccur = _cooccurrence(history[-window:])
            centers = _cluster_centers(cooccur, top_k=3)
            if centers:
                bet = _expand_anchor(centers[0], cooccur)
                if bet and bet not in bets:
                    bets.append(bet)
    if len(bets) < 5:
        bet = _triplet(history)
        if bet and bet not in bets:
            bets.append(bet)
    if len(bets) < 5:
        bet = _gap_compensation(history)
        if bet and bet not in bets:
            bets.append(bet)
    return bets[:5]


def _cluster_enhancements(
    history: tuple[tuple[int, ...], ...],
) -> _RawPortfolio:
    configurations = (
        [_cluster_base(history)],
        [_triplet(history)],
        [_temporal(history)],
        [_gap_compensation(history)],
        [_graph_community(history)],
        [_anti_cooccur(history)],
        _orthogonal_four(history),
        _hybrid_five(history),
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


def _optimize_third_bet(
    history: tuple[tuple[int, ...], ...],
) -> _RawPortfolio:
    used = set(_FROZEN_PURCHASED_BET_1) | set(
        _FROZEN_PURCHASED_BET_2
    )
    tails_covered = {number % 10 for number in used}
    tails_missing = set(range(10)) - tails_covered
    zone_ranges = ((1, 10), (11, 20), (21, 30), (31, 40), (41, 49))
    zone_counts = [0] * 5
    for number in used:
        for index, (lower, upper) in enumerate(zone_ranges):
            if lower <= number <= upper:
                zone_counts[index] += 1
                break
    weakest_index = zone_counts.index(min(zone_counts))
    weakest_lower, weakest_upper = zone_ranges[weakest_index]
    recent_frequency: Counter[int] = Counter(
        number for draw in history[-50:] for number in draw
    )
    expected = 50 * 6 / 49
    gaps: dict[int, int] = {}
    for number in range(1, 50):
        for index, draw in enumerate(reversed(history)):
            if number in draw:
                gaps[number] = index
                break
        else:
            gaps[number] = len(history)
    candidates = [number for number in range(1, 50) if number not in used]
    scores: dict[int, int] = {}
    for number in candidates:
        score = 0
        if number % 10 in tails_missing:
            score += 3
        if weakest_lower <= number <= weakest_upper:
            score += 3
        if abs(recent_frequency.get(number, 0) - expected) > 2:
            score += 1
        if gaps.get(number, 0) > (49 / 6) * 1.5:
            score += 1
        scores[number] = score
    ranked = sorted(candidates, key=lambda number: scores[number], reverse=True)
    top_candidates = ranked[:20]
    weak_zone_candidates = [
        number
        for number in candidates
        if weakest_lower <= number <= weakest_upper
    ]
    for number in weak_zone_candidates[:3]:
        if number not in top_candidates:
            top_candidates.append(number)
    best_combo: list[int] | None = None
    best_total = -1
    for raw_combo in combinations(top_candidates, 6):
        bet = sorted(raw_combo)
        structure = _structural_score(bet)
        candidate_score = sum(scores[number] for number in raw_combo)
        new_tails = {number % 10 for number in raw_combo}
        tail_fill = len(new_tails & tails_missing)
        zone_fill = sum(
            1
            for number in raw_combo
            if weakest_lower <= number <= weakest_upper
        )
        total = (
            structure * 2
            + candidate_score
            + tail_fill * 2
            + min(zone_fill, 2) * 2
        )
        if total > best_total:
            best_total = total
            best_combo = bet
    if best_combo is None:
        raise LegacySourceNativeWave8SourceError(
            "FROZEN_SOURCE_NO_NATIVE_TICKETS"
        )
    candidate_k = len(top_candidates)
    return _RawPortfolio(
        tickets=(best_combo,),
        source_candidate_ticket_counts=(candidate_k,),
        source_runtime_parameters=(
            f"purchased_bet_1={','.join(map(str, _FROZEN_PURCHASED_BET_1))}",
            f"purchased_bet_2={','.join(map(str, _FROZEN_PURCHASED_BET_2))}",
            f"weakest_zone={weakest_lower}-{weakest_upper}",
        ),
        candidate_k=candidate_k,
        candidate_combination_count=math.comb(candidate_k, 6),
    )


def _raw_portfolio(
    request: LegacySourceNativeWave8Request,
) -> _RawPortfolio:
    history = _history_numbers(request.history)
    if request.legacy_method_id == GEMINI_PHASE2_METHOD_ID:
        return _gemini_phase2(history)
    if request.legacy_method_id == DYNAMIC_FREQUENCY_METHOD_ID:
        return _dynamic_frequency(history)
    if request.legacy_method_id == CLUSTER_ENHANCEMENTS_METHOD_ID:
        return _cluster_enhancements(history)
    return _optimize_third_bet(history)


def generate_legacy_source_native_wave8_portfolio(
    request: LegacySourceNativeWave8Request,
) -> LegacySourceNativeWave8Result:
    """Generate source-ordered native tickets from strictly prior history."""

    _validate_request(request)
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE8_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave8Error(
            f"method requires at least {minimum} history draws"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    raw = _raw_portfolio(request)
    if not raw.tickets:
        raise LegacySourceNativeWave8SourceError(
            "FROZEN_SOURCE_NO_NATIVE_TICKETS"
        )
    tickets = tuple(_ticket(ticket) for ticket in raw.tickets)
    return LegacySourceNativeWave8Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave8Metadata(
            protocol=SOURCE_NATIVE_WAVE8_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE8_METHOD[
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
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE8_METHOD[
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
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE8_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_candidate_ticket_counts=(
                raw.source_candidate_ticket_counts
            ),
            source_runtime_parameters=raw.source_runtime_parameters,
            candidate_k=None,
            candidate_combination_count=None,
            combination_count=None,
        ),
    )


__all__ = [
    "CANDIDATE_K_BY_SOURCE_NATIVE_WAVE8_METHOD",
    "CLUSTER_ENHANCEMENTS_METHOD_ID",
    "DEFAULT_SOURCE_NATIVE_WAVE8_USER_SEED",
    "DYNAMIC_FREQUENCY_METHOD_ID",
    "GEMINI_PHASE2_METHOD_ID",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE8_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE8_METHOD",
    "OPTIMIZE_THIRD_BET_METHOD_ID",
    "RANDOM_PROTOCOL_BY_SOURCE_NATIVE_WAVE8_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE8_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE8_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE8_METHOD",
    "SOURCE_NATIVE_WAVE8_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE8_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE8_METHODS",
    "LegacySourceNativeWave8Error",
    "LegacySourceNativeWave8Metadata",
    "LegacySourceNativeWave8Request",
    "LegacySourceNativeWave8Result",
    "LegacySourceNativeWave8SourceError",
    "generate_legacy_source_native_wave8_portfolio",
]
