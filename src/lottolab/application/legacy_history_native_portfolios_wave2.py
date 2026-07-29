"""Faithful ports of the second frozen BIG_LOTTO history-native batch."""

from __future__ import annotations

import hashlib
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Final

from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
    LegacyNumpyRandomState,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

HISTORY_NATIVE_WAVE2_PROTOCOL = "legacy_history_native_wave2/v1"
DEFAULT_HISTORY_NATIVE_WAVE2_USER_SEED = (
    "biglotto-full-universe-history-native-wave2-v1"
)
ANTI_CONSENSUS_METHOD_ID = "lottery_api/models/anti_consensus_strategy.py"
CONSTRAINT_FILTER_METHOD_ID = (
    "lottery_api/models/constraint_filter_predictor.py"
)
COOCCURRENCE_GRAPH_METHOD_ID = "lottery_api/models/cooccurrence_graph.py"
CONCENTRATED_POOL_METHOD_ID = (
    "lottery_api/models/concentrated_pool_predictor.py"
)
SUPPORTED_HISTORY_NATIVE_WAVE2_METHODS = (
    ANTI_CONSENSUS_METHOD_ID,
    CONSTRAINT_FILTER_METHOD_ID,
    COOCCURRENCE_GRAPH_METHOD_ID,
    CONCENTRATED_POOL_METHOD_ID,
)
SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE2_METHOD: Final = {
    ANTI_CONSENSUS_METHOD_ID: (
        "a454ddd26cef405db5e9b4b4f5d2c0f5e1df14d291bbd0505d45be36a2cecc80"
    ),
    CONSTRAINT_FILTER_METHOD_ID: (
        "3a85b3995002a9c66c50643e2b52a3cdc853c8e858242c7f335ce8736d576c85"
    ),
    COOCCURRENCE_GRAPH_METHOD_ID: (
        "25fa2e47309232265f442a688ddc1de2bbd853ce6c63762a5298aef016c008ab"
    ),
    CONCENTRATED_POOL_METHOD_ID: (
        "a03b9070574950b634376ac944dbc58b503c188f47850a23a2de065a85e7fc8b"
    ),
}
MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE2_METHOD: Final = {
    ANTI_CONSENSUS_METHOD_ID: 1,
    CONSTRAINT_FILTER_METHOD_ID: 1,
    COOCCURRENCE_GRAPH_METHOD_ID: 100,
    CONCENTRATED_POOL_METHOD_ID: 1,
}
NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE2_METHOD: Final = {
    ANTI_CONSENSUS_METHOD_ID: "EXACTLY_6",
    CONSTRAINT_FILTER_METHOD_ID: "EXACTLY_2",
    COOCCURRENCE_GRAPH_METHOD_ID: "SOURCE_ORDER_UP_TO_4_UNIQUE",
    CONCENTRATED_POOL_METHOD_ID: "EXACTLY_2",
}
RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE2_METHOD: Final = {
    ANTI_CONSENSUS_METHOD_ID: "numpy.random.RandomState(MT19937)",
    CONSTRAINT_FILTER_METHOD_ID: (
        "numpy.random.RandomState(MT19937)+random.Random(MT19937)_fallback"
    ),
    COOCCURRENCE_GRAPH_METHOD_ID: (
        "numpy.random.RandomState(MT19937)+random.Random(MT19937)_fallback"
    ),
    CONCENTRATED_POOL_METHOD_ID: "NONE_DETERMINISTIC",
}
SOURCE_HISTORY_ORDER_BY_HISTORY_NATIVE_WAVE2_METHOD: Final = {
    ANTI_CONSENSUS_METHOD_ID: "RECENT_FIRST",
    CONSTRAINT_FILTER_METHOD_ID: "RECENT_FIRST",
    COOCCURRENCE_GRAPH_METHOD_ID: "OLDEST_FIRST",
    CONCENTRATED_POOL_METHOD_ID: "RECENT_FIRST",
}
CANDIDATE_K_BY_HISTORY_NATIVE_WAVE2_METHOD: Final = {
    ANTI_CONSENSUS_METHOD_ID: None,
    CONSTRAINT_FILTER_METHOD_ID: None,
    COOCCURRENCE_GRAPH_METHOD_ID: 20,
    CONCENTRATED_POOL_METHOD_ID: 28,
}

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6


class LegacyHistoryNativeWave2Error(ValueError):
    """A request cannot satisfy the second history-native batch contract."""


class LegacyHistoryNativeWave2SourceError(LegacyHistoryNativeWave2Error):
    """A frozen source produced output outside its preserved contract."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacyHistoryNativeWave2Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_HISTORY_NATIVE_WAVE2_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacyHistoryNativeWave2Metadata:
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
    history_draw_count: int
    history_first_draw_number: str
    history_cutoff_draw_number: str
    source_history_order: str
    native_ticket_count: int
    native_ticket_count_semantics: str
    native_ticket_order: str
    native_duplicate_ticket_count: int
    candidate_k: int | None
    combination_count: None

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacyHistoryNativeWave2Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacyHistoryNativeWave2Metadata


@dataclass(slots=True)
class _NumberScore:
    number: int
    frequency_score: float = 0.0
    gap_score: float = 0.0
    zone_score: float = 0.0
    trend_score: float = 0.0
    pair_score: float = 0.0
    total_score: float = 0.0


def _ticket(numbers: list[int]) -> Ticket:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(not _MIN_NUMBER <= number <= _MAX_NUMBER for number in values)
    ):
        raise LegacyHistoryNativeWave2SourceError(
            "FROZEN_SOURCE_INVALID_TICKET"
        )
    return values


def _validate_request(request: LegacyHistoryNativeWave2Request) -> None:
    if (
        request.legacy_method_id
        not in SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE2_METHOD
    ):
        raise LegacyHistoryNativeWave2Error(
            "legacy method is outside the second history-native batch"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
    ):
        raise LegacyHistoryNativeWave2Error(
            "target draw number must be non-empty"
        )
    if type(request.replicate_id) is not int or request.replicate_id < 0:
        raise LegacyHistoryNativeWave2Error(
            "replicate_id must be a non-negative integer"
        )
    if type(request.user_seed) not in (str, int):
        raise LegacyHistoryNativeWave2Error(
            "user_seed must be a string or integer"
        )
    seen: set[str] = set()
    for draw in request.history:
        if not draw.draw_number or draw.draw_number in seen:
            raise LegacyHistoryNativeWave2Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)
        _ticket(list(draw.numbers))


def _seed(
    request: LegacyHistoryNativeWave2Request,
) -> tuple[str, str, int]:
    source_sha256 = SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE2_METHOD[
        request.legacy_method_id
    ]
    material = "|".join(
        (
            HISTORY_NATIVE_WAVE2_PROTOCOL,
            request.legacy_method_id,
            source_sha256,
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _numpy_pairwise_sum(values: list[float]) -> float:
    if len(values) < 8:
        result = -0.0
        for value in values:
            result += value
        return result
    if len(values) <= 128:
        partial = list(values[:8])
        index = 8
        aligned_end = len(values) - (len(values) % 8)
        while index < aligned_end:
            for offset in range(8):
                partial[offset] += values[index + offset]
            index += 8
        result = (
            (partial[0] + partial[1]) + (partial[2] + partial[3])
        ) + (
            (partial[4] + partial[5]) + (partial[6] + partial[7])
        )
        while index < len(values):
            result += values[index]
            index += 1
        return result
    midpoint = len(values) // 2
    midpoint -= midpoint % 8
    return _numpy_pairwise_sum(
        values[:midpoint]
    ) + _numpy_pairwise_sum(values[midpoint:])


def _is_arithmetic_sequence(numbers: list[int]) -> bool:
    if len(numbers) < 3:
        return False
    differences = [
        numbers[index + 1] - numbers[index]
        for index in range(len(numbers) - 1)
    ]
    return len(set(differences)) == 1


def _anti_consensus_score(numbers: list[int]) -> float:
    birthday_count = sum(number <= 31 for number in numbers)
    score = birthday_count / len(numbers) * 50
    score += sum(
        number in {6, 8, 9, 18, 28, 38} for number in numbers
    ) * 10
    score -= sum(number in {4, 13, 14} for number in numbers) * 5
    sorted_numbers = sorted(numbers)
    score += sum(
        sorted_numbers[index + 1] - sorted_numbers[index] == 1
        for index in range(len(sorted_numbers) - 1)
    ) * 15
    symmetry_count = sum(50 - number in numbers for number in numbers)
    score += symmetry_count / 2 * 10
    if _is_arithmetic_sequence(sorted_numbers):
        score += 30
    tails = [number % 10 for number in numbers]
    score += (len(tails) - len(set(tails))) * 8
    odd_count = sum(number % 2 == 1 for number in numbers)
    if odd_count == 0 or odd_count == len(numbers):
        score += 20
    if sum(numbers) % 10 == 0:
        score += 15
    return score


def _has_common_patterns(numbers: list[int]) -> bool:
    sorted_numbers = sorted(numbers)
    if any(
        sorted_numbers[index + 1] - sorted_numbers[index] == 1
        for index in range(len(sorted_numbers) - 1)
    ):
        return True
    if _is_arithmetic_sequence(sorted_numbers):
        return True
    odd_count = sum(number % 2 == 1 for number in numbers)
    return odd_count == 0 or odd_count == len(numbers)


def _anti_consensus(seed_integer: int) -> tuple[Ticket, ...]:
    rng = LegacyNumpyRandomState(seed_integer % (2**32))
    results: list[tuple[float, Ticket]] = []
    large_numbers = list(range(32, _MAX_NUMBER + 1))
    for _ in range(3):
        selected = rng.choice_without_replacement(
            large_numbers,
            _PICK_COUNT,
        )
        results.append((_anti_consensus_score(selected), _ticket(selected)))

    unlucky_heavy = list({4, 13, 14})
    remaining = [
        number
        for number in range(1, _MAX_NUMBER + 1)
        if number not in unlucky_heavy
    ]
    for _ in range(3):
        selected = rng.choice_without_replacement(unlucky_heavy, 2)
        needed = _PICK_COUNT - len(selected)
        candidates = [number for number in remaining if number >= 32]
        if len(candidates) < needed:
            candidates = remaining
        selected.extend(
            rng.choice_without_replacement(candidates, needed)
        )
        results.append((_anti_consensus_score(selected), _ticket(selected)))

    for _ in range(3):
        best_score = float("inf")
        best_numbers: list[int] | None = None
        for _attempt in range(1000):
            selected = rng.choice_without_replacement(
                list(range(1, 32)),
                2,
            )
            selected.extend(
                rng.choice_without_replacement(
                    list(range(32, _MAX_NUMBER + 1)),
                    4,
                )
            )
            consensus = _anti_consensus_score(selected)
            if _has_common_patterns(selected):
                continue
            if consensus < best_score:
                best_score = consensus
                best_numbers = selected
        if best_numbers is not None:
            results.append((best_score, _ticket(best_numbers)))
    results.sort(key=lambda item: item[0])
    return tuple(ticket for _score, ticket in results[:6])


def _constraint_passes(numbers: list[int]) -> bool:
    odd_count = sum(number % 2 == 1 for number in numbers)
    if not 2 <= odd_count <= 4:
        return False
    zones = ((1, 10), (11, 20), (21, 30), (31, 40), (41, 49))
    zones_covered = {
        index
        for number in numbers
        for index, (low, high) in enumerate(zones)
        if low <= number <= high
    }
    if len(zones_covered) < 3:
        return False
    if not 120 <= sum(numbers) <= 180:
        return False
    sorted_numbers = sorted(numbers)
    longest = 1
    current = 1
    for index in range(1, len(sorted_numbers)):
        if sorted_numbers[index] == sorted_numbers[index - 1] + 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    if longest > 2:
        return False
    return len({number % 10 for number in numbers}) >= 4


def _constraint_weights(
    recent_first: tuple[LegacyHistoryDraw, ...],
) -> dict[int, float]:
    recent = recent_first[:100]
    frequency = Counter(
        number for draw in recent for number in draw.numbers
    )
    last_seen = {number: 100 for number in range(1, 50)}
    for index, draw in enumerate(recent):
        for number in draw.numbers:
            if last_seen[number] == 100:
                last_seen[number] = index
    maximum_frequency = max(frequency.values()) if frequency else 1
    weights: dict[int, float] = {}
    for number in range(1, 50):
        frequency_score = frequency.get(number, 0) / maximum_frequency
        gap = last_seen[number]
        if gap < 8:
            gap_score = gap / 8 * 0.5
        elif gap <= 15:
            gap_score = 1.0
        else:
            gap_score = max(0.3, 0.9 ** ((gap - 15) / 5))
        weights[number] = 0.5 * frequency_score + 0.5 * gap_score
    return weights


def _constraint_combination(
    weights: dict[int, float],
    numpy_rng: LegacyNumpyRandomState,
    python_rng: random.Random,
) -> Ticket:
    numbers = list(weights)
    raw_probabilities = [weights[number] for number in numbers]
    total = _numpy_pairwise_sum(raw_probabilities)
    probabilities = [value / total for value in raw_probabilities]
    for _ in range(1000):
        selected = numpy_rng.choice_without_replacement(
            numbers,
            _PICK_COUNT,
            probabilities=probabilities,
        )
        if _constraint_passes(selected):
            return _ticket(selected)
    return _ticket(python_rng.sample(numbers, _PICK_COUNT))


def _constraint_filter(
    history: tuple[LegacyHistoryDraw, ...],
    seed_integer: int,
) -> tuple[Ticket, ...]:
    recent_first = tuple(reversed(history))
    weights = _constraint_weights(recent_first)
    numpy_rng = LegacyNumpyRandomState(seed_integer % (2**32))
    python_rng = random.Random()
    python_rng.seed(seed_integer, version=2)
    tickets: list[Ticket] = []
    all_used: set[int] = set()
    for bet_index in range(2):
        adjusted = {
            number: (
                weight
                if bet_index == 0
                else weight * (0.3 if number in all_used else 1.2)
            )
            for number, weight in weights.items()
        }
        ticket = _constraint_combination(
            adjusted,
            numpy_rng,
            python_rng,
        )
        tickets.append(ticket)
        all_used.update(ticket)
    return tuple(tickets)


class _CooccurrenceGraph:
    def __init__(self) -> None:
        self.edges: defaultdict[tuple[int, int], int] = defaultdict(int)

    def build(
        self,
        history: tuple[LegacyHistoryDraw, ...],
    ) -> None:
        self.edges.clear()
        for draw in history[-100:]:
            for first, second in combinations(sorted(draw.numbers), 2):
                self.edges[(first, second)] += 1

    def degree_centrality(self) -> dict[int, float]:
        degrees: Counter[int] = Counter()
        for (first, second), weight in self.edges.items():
            degrees[first] += weight
            degrees[second] += weight
        maximum = max(degrees.values()) if degrees else 1
        return {
            number: degree / maximum
            for number, degree in degrees.items()
        }

    def neighbors(self, node: int) -> list[tuple[int, int]]:
        neighbors: list[tuple[int, int]] = []
        for (first, second), weight in self.edges.items():
            if first == node:
                neighbors.append((second, weight))
            elif second == node:
                neighbors.append((first, weight))
        return sorted(neighbors, key=lambda item: -item[1])

    def pagerank(self) -> dict[int, float]:
        node_set: set[int] = set()
        for first, second in self.edges:
            node_set.add(first)
            node_set.add(second)
        count = len(node_set)
        if count == 0:
            return {}
        nodes = list(node_set)
        rank = {node: 1 / count for node in nodes}
        adjacency: defaultdict[int, list[tuple[int, int]]] = defaultdict(list)
        for (first, second), weight in self.edges.items():
            adjacency[first].append((second, weight))
            adjacency[second].append((first, weight))
        outgoing_by_node = {
            node: sum(weight for _neighbor, weight in adjacency[node])
            for node in nodes
        }
        for _ in range(100):
            next_rank: dict[int, float] = {}
            for node in nodes:
                value = (1 - 0.85) / count
                for neighbor, weight in adjacency[node]:
                    outgoing = outgoing_by_node[neighbor]
                    if outgoing > 0:
                        value += (
                            0.85
                            * rank[neighbor]
                            * weight
                            / outgoing
                        )
                next_rank[node] = value
            rank = next_rank
        return rank

    def communities(self) -> list[set[int]]:
        maximum = max(self.edges.values()) if self.edges else 1
        strong_edges = {
            (first, second)
            for (first, second), weight in self.edges.items()
            if weight / maximum > 0.2
        }
        parent: dict[int, int] = {}

        def find(number: int) -> int:
            if number not in parent:
                parent[number] = number
            if parent[number] != number:
                parent[number] = find(parent[number])
            return parent[number]

        def union(first: int, second: int) -> None:
            first_parent = find(first)
            second_parent = find(second)
            if first_parent != second_parent:
                parent[first_parent] = second_parent

        for first, second in strong_edges:
            union(first, second)
        communities: defaultdict[int, set[int]] = defaultdict(set)
        for first, second in strong_edges:
            communities[find(first)].add(first)
            communities[find(first)].add(second)
        return list(communities.values())


def _cooccurrence_graph(
    history: tuple[LegacyHistoryDraw, ...],
    seed_integer: int,
) -> tuple[Ticket, ...]:
    graph = _CooccurrenceGraph()
    graph.build(history)
    predictions: list[Ticket] = []
    page_rank = graph.pagerank()
    if page_rank:
        top_nodes = sorted(
            page_rank.items(),
            key=lambda item: -item[1],
        )[:_PICK_COUNT]
        predictions.append(_ticket([number for number, _ in top_nodes]))
    centrality = graph.degree_centrality()
    if centrality:
        top_nodes = sorted(
            centrality.items(),
            key=lambda item: -item[1],
        )[:_PICK_COUNT]
        candidate = _ticket([number for number, _ in top_nodes])
        if candidate not in predictions:
            predictions.append(candidate)
    for community in sorted(
        graph.communities(),
        key=len,
        reverse=True,
    )[:2]:
        if len(community) >= _PICK_COUNT:
            candidate = _ticket(list(community)[:_PICK_COUNT])
        else:
            values = list(community)
            for node in community:
                for neighbor, _weight in graph.neighbors(node):
                    if neighbor not in values:
                        values.append(neighbor)
                    if len(values) >= _PICK_COUNT:
                        break
                if len(values) >= _PICK_COUNT:
                    break
            while len(values) < _PICK_COUNT:
                for number in range(1, _MAX_NUMBER + 1):
                    if number not in values:
                        values.append(number)
                        break
            candidate = _ticket(values[:_PICK_COUNT])
        if candidate not in predictions:
            predictions.append(candidate)

    numpy_rng = LegacyNumpyRandomState(seed_integer % (2**32))
    python_rng = random.Random()
    python_rng.seed(seed_integer, version=2)
    while len(predictions) < 4:
        if not page_rank:
            candidate = _ticket(
                python_rng.sample(range(1, _MAX_NUMBER + 1), _PICK_COUNT)
            )
        else:
            candidates = [
                number
                for number, _score in sorted(
                    page_rank.items(),
                    key=lambda item: -item[1],
                )[:20]
            ]
            weights = [page_rank[number] for number in candidates]
            total = sum(weights)
            probabilities = (
                [1 / len(candidates)] * len(candidates)
                if total == 0
                else [weight / total for weight in weights]
            )
            try:
                candidate = _ticket(
                    numpy_rng.choice_without_replacement(
                        candidates,
                        min(_PICK_COUNT, len(candidates)),
                        probabilities=probabilities,
                    )
                )
            except ValueError:
                candidate = _ticket(
                    python_rng.sample(
                        candidates,
                        min(_PICK_COUNT, len(candidates)),
                    )
                )
        if candidate not in predictions:
            predictions.append(candidate)
        else:
            break
    return tuple(predictions[:4])


_ZONES = ((1, 10), (11, 20), (21, 30), (31, 40), (41, 49))


def _concentrated_pool(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[Ticket, ...]:
    recent_first = tuple(reversed(history))
    frequency_history = recent_first[:50]
    frequency = Counter(
        number for draw in frequency_history for number in draw.numbers
    )
    maximum_frequency = max(frequency.values()) if frequency else 1
    frequency_scores = {
        number: frequency.get(number, 0) / maximum_frequency
        for number in range(1, 50)
    }

    last_seen = {number: len(recent_first) for number in range(1, 50)}
    for index, draw in enumerate(recent_first):
        for number in draw.numbers:
            if last_seen[number] == len(recent_first):
                last_seen[number] = index
    ideal_gap = 49 / 6
    gap_scores: dict[int, float] = {}
    for number, gap in last_seen.items():
        optimal_low = ideal_gap * 1.2
        optimal_high = ideal_gap * 2.5
        if gap < optimal_low:
            gap_scores[number] = gap / optimal_low * 0.5
        elif gap <= optimal_high:
            gap_scores[number] = 1.0
        else:
            gap_scores[number] = max(
                0.3,
                0.9 ** ((gap - optimal_high) / ideal_gap),
            )

    zone_frequency: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for draw in recent_first[:30]:
        for number in draw.numbers:
            for zone_index, (low, high) in enumerate(_ZONES):
                if low <= number <= high:
                    zone_frequency[zone_index][number] += 1
                    break
    zone_scores: dict[int, float] = {}
    for zone_index, (low, high) in enumerate(_ZONES):
        counter = zone_frequency[zone_index]
        maximum = max(counter.values()) if counter else 1
        for number in range(low, high + 1):
            zone_scores[number] = counter.get(number, 0) / maximum

    short_window = min(10, len(recent_first))
    long_window = min(50, len(recent_first))
    short_frequency = Counter(
        number
        for draw in recent_first[:short_window]
        for number in draw.numbers
    )
    long_frequency = Counter(
        number
        for draw in recent_first[:long_window]
        for number in draw.numbers
    )
    trend_scores: dict[int, float] = {}
    for number in range(1, 50):
        short_rate = short_frequency.get(number, 0) / short_window
        long_rate = long_frequency.get(number, 0) / long_window
        trend_ratio = (
            short_rate / long_rate
            if long_rate > 0
            else 1.0
            if short_rate > 0
            else 0.5
        )
        if trend_ratio >= 1.5:
            trend_scores[number] = 1.0
        elif trend_ratio >= 1.0:
            trend_scores[number] = 0.6 + 0.4 * (
                trend_ratio - 1.0
            ) / 0.5
        elif trend_ratio >= 0.5:
            trend_scores[number] = 0.3 + 0.3 * (
                trend_ratio - 0.5
            ) / 0.5
        else:
            trend_scores[number] = 0.3 * trend_ratio / 0.5

    pair_count: defaultdict[tuple[int, int], int] = defaultdict(int)
    for draw in recent_first[:100]:
        numbers = draw.numbers
        for index, first in enumerate(numbers):
            for second in numbers[index + 1 :]:
                pair_count[(min(first, second), max(first, second))] += 1
    pair_heat: defaultdict[int, float] = defaultdict(float)
    for (first, second), count in pair_count.items():
        pair_heat[first] += count
        pair_heat[second] += count
    maximum_heat = max(pair_heat.values()) if pair_heat else 1
    pair_scores = {
        number: pair_heat.get(number, 0) / maximum_heat
        for number in range(1, 50)
    }

    pool: list[_NumberScore] = []
    for number in range(1, 50):
        score = _NumberScore(
            number=number,
            frequency_score=frequency_scores[number],
            gap_score=gap_scores[number],
            zone_score=zone_scores[number],
            trend_score=trend_scores[number],
            pair_score=pair_scores[number],
        )
        score.total_score = (
            0.25 * score.frequency_score
            + 0.20 * score.gap_score
            + 0.15 * score.zone_score
            + 0.25 * score.trend_score
            + 0.15 * score.pair_score
        )
        pool.append(score)
    pool.sort(key=lambda item: -item.total_score)
    pool = pool[:28]

    selected: list[int] = []
    zone_counts = [0] * len(_ZONES)
    target_per_zone = _PICK_COUNT / len(_ZONES)
    for score in sorted(pool, key=lambda item: -item.total_score):
        if len(selected) >= _PICK_COUNT:
            break
        zone_index = next(
            (
                index
                for index, (low, high) in enumerate(_ZONES)
                if low <= score.number <= high
            ),
            None,
        )
        if (
            zone_index is not None
            and zone_counts[zone_index] < target_per_zone + 0.5
        ):
            selected.append(score.number)
            zone_counts[zone_index] += 1
    if len(selected) < _PICK_COUNT:
        remaining = [
            score.number
            for score in pool
            if score.number not in selected
        ]
        selected.extend(remaining[: _PICK_COUNT - len(selected)])
    first_ticket = _ticket(selected[:_PICK_COUNT])
    remaining_pool = [
        score for score in pool if score.number not in first_ticket
    ]
    if len(remaining_pool) < _PICK_COUNT:
        raise LegacyHistoryNativeWave2SourceError(
            "FROZEN_SOURCE_CONCENTRATED_POOL_TOO_SMALL"
        )
    remaining_pool.sort(
        key=lambda item: -(item.gap_score * 0.6 + item.total_score * 0.4)
    )
    second_ticket = _ticket(
        [score.number for score in remaining_pool[:_PICK_COUNT]]
    )
    return (first_ticket, second_ticket)


def generate_legacy_history_native_wave2_portfolio(
    request: LegacyHistoryNativeWave2Request,
) -> LegacyHistoryNativeWave2Result:
    """Generate source-ordered native tickets from strictly prior history."""

    _validate_request(request)
    minimum_history = MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE2_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum_history:
        raise LegacyHistoryNativeWave2Error(
            f"method requires at least {minimum_history} history draws"
        )
    seed_material, seed_digest, seed_integer = _seed(request)
    if request.legacy_method_id == ANTI_CONSENSUS_METHOD_ID:
        tickets = _anti_consensus(seed_integer)
    elif request.legacy_method_id == CONSTRAINT_FILTER_METHOD_ID:
        tickets = _constraint_filter(request.history, seed_integer)
    elif request.legacy_method_id == COOCCURRENCE_GRAPH_METHOD_ID:
        tickets = _cooccurrence_graph(request.history, seed_integer)
    else:
        tickets = _concentrated_pool(request.history)
    if not tickets or len(tickets) > 6:
        raise LegacyHistoryNativeWave2SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    expected_counts = {
        ANTI_CONSENSUS_METHOD_ID: 6,
        CONSTRAINT_FILTER_METHOD_ID: 2,
        CONCENTRATED_POOL_METHOD_ID: 2,
    }
    expected = expected_counts.get(request.legacy_method_id)
    if expected is not None and len(tickets) != expected:
        raise LegacyHistoryNativeWave2SourceError(
            "FROZEN_SOURCE_NATIVE_TICKET_COUNT_CHANGED"
        )
    random_protocol = RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE2_METHOD[
        request.legacy_method_id
    ]
    return LegacyHistoryNativeWave2Result(
        tickets=tickets,
        metadata=LegacyHistoryNativeWave2Metadata(
            protocol=HISTORY_NATIVE_WAVE2_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE2_METHOD[
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
            history_draw_count=len(request.history),
            history_first_draw_number=request.history[0].draw_number,
            history_cutoff_draw_number=request.history[-1].draw_number,
            source_history_order=(
                SOURCE_HISTORY_ORDER_BY_HISTORY_NATIVE_WAVE2_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE2_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_order="FROZEN_SOURCE_ENTRYPOINT_ORDER",
            native_duplicate_ticket_count=len(tickets) - len(set(tickets)),
            candidate_k=None,
            combination_count=None,
        ),
    )


__all__ = [
    "ANTI_CONSENSUS_METHOD_ID",
    "CANDIDATE_K_BY_HISTORY_NATIVE_WAVE2_METHOD",
    "CONCENTRATED_POOL_METHOD_ID",
    "CONSTRAINT_FILTER_METHOD_ID",
    "COOCCURRENCE_GRAPH_METHOD_ID",
    "DEFAULT_HISTORY_NATIVE_WAVE2_USER_SEED",
    "HISTORY_NATIVE_WAVE2_PROTOCOL",
    "MINIMUM_HISTORY_BY_HISTORY_NATIVE_WAVE2_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_HISTORY_NATIVE_WAVE2_METHOD",
    "RANDOM_PROTOCOL_BY_HISTORY_NATIVE_WAVE2_METHOD",
    "SOURCE_HISTORY_ORDER_BY_HISTORY_NATIVE_WAVE2_METHOD",
    "SOURCE_SHA256_BY_HISTORY_NATIVE_WAVE2_METHOD",
    "SUPPORTED_HISTORY_NATIVE_WAVE2_METHODS",
    "LegacyHistoryNativeWave2Error",
    "LegacyHistoryNativeWave2Metadata",
    "LegacyHistoryNativeWave2Request",
    "LegacyHistoryNativeWave2Result",
    "LegacyHistoryNativeWave2SourceError",
    "generate_legacy_history_native_wave2_portfolio",
]
