"""DB-free port of the frozen BIG_LOTTO co-occurrence graph method.

The donor is ``lottery_api/models/cooccurrence_graph.py`` from frozen commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9``. This module keeps the audited
history-native graph, PageRank, degree-centrality, community, and seeded
fallback sequence inline because the strategy layer must not import the
application-layer reference oracle.
"""

from __future__ import annotations

import hashlib
import random
from collections import Counter, defaultdict
from itertools import combinations

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter

_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_NATIVE_TICKET_COUNT = 4
_MINIMUM_HISTORY = 100

_HISTORY_NATIVE_WAVE2_PROTOCOL = "legacy_history_native_wave2/v1"
_HISTORY_NATIVE_WAVE2_DEFAULT_USER_SEED = (
    "biglotto-full-universe-history-native-wave2-v1"
)
_METHOD_ID = "lottery_api/models/cooccurrence_graph.py"
_SOURCE_SHA256 = "25fa2e47309232265f442a688ddc1de2bbd853ce6c63762a5298aef016c008ab"
_REPLICATE_ID = 0


class _LegacyNumpyRandomState:
    """Minimal NumPy ``RandomState`` MT19937 sampling used by the donor."""

    _STATE_SIZE = 624
    _PERIOD_OFFSET = 397
    _MATRIX_A = 0x9908B0DF
    _UPPER_MASK = 0x80000000
    _LOWER_MASK = 0x7FFFFFFF

    def __init__(self, seed: int) -> None:
        self._state = [0] * self._STATE_SIZE
        self._state[0] = seed & 0xFFFFFFFF
        for index in range(1, self._STATE_SIZE):
            previous = self._state[index - 1]
            self._state[index] = (
                1812433253 * (previous ^ (previous >> 30)) + index
            ) & 0xFFFFFFFF
        self._index = self._STATE_SIZE

    def _twist(self) -> None:
        for index in range(self._STATE_SIZE):
            combined = (
                self._state[index] & self._UPPER_MASK
            ) | (
                self._state[(index + 1) % self._STATE_SIZE]
                & self._LOWER_MASK
            )
            value = self._state[
                (index + self._PERIOD_OFFSET) % self._STATE_SIZE
            ] ^ (combined >> 1)
            if combined & 1:
                value ^= self._MATRIX_A
            self._state[index] = value
        self._index = 0

    def _next_uint32(self) -> int:
        if self._index >= self._STATE_SIZE:
            self._twist()
        value = self._state[self._index]
        self._index += 1
        value ^= value >> 11
        value ^= (value << 7) & 0x9D2C5680
        value ^= (value << 15) & 0xEFC60000
        value ^= value >> 18
        return value & 0xFFFFFFFF

    def _double(self) -> float:
        first = self._next_uint32() >> 5
        second = self._next_uint32() >> 6
        return (first * 67108864.0 + second) / 9007199254740992.0

    def _interval(self, maximum: int) -> int:
        if maximum < 0:
            raise ValueError("maximum must be non-negative")
        if maximum == 0:
            return 0
        mask = maximum
        mask |= mask >> 1
        mask |= mask >> 2
        mask |= mask >> 4
        mask |= mask >> 8
        mask |= mask >> 16
        while True:
            value = self._next_uint32() & mask
            if value <= maximum:
                return value

    def permutation(self, values: list[int]) -> list[int]:
        result = list(values)
        for index in range(len(result) - 1, 0, -1):
            swap_index = self._interval(index)
            result[index], result[swap_index] = (
                result[swap_index],
                result[index],
            )
        return result

    def choice_without_replacement(
        self,
        values: list[int],
        size: int,
        *,
        probabilities: list[float] | None = None,
    ) -> list[int]:
        if size < 0 or size > len(values):
            raise ValueError("sample size is outside the population")
        if probabilities is None:
            indices = self.permutation(list(range(len(values))))[:size]
            return [values[index] for index in indices]
        if len(probabilities) != len(values):
            raise ValueError("probability vector length must match population")
        if sum(value > 0.0 for value in probabilities) < size:
            raise ValueError("fewer positive probabilities than sample size")
        remaining_probabilities = list(probabilities)
        found: list[int] = []
        while len(found) < size:
            sample_count = size - len(found)
            for index in found:
                remaining_probabilities[index] = 0.0
            cumulative: list[float] = []
            running = 0.0
            for probability in remaining_probabilities:
                running += probability
                cumulative.append(running)
            if running <= 0.0:
                raise ValueError("probabilities must contain positive mass")
            cumulative = [value / running for value in cumulative]
            new_indices: list[int] = []
            for _ in range(sample_count):
                sample = self._double()
                index = 0
                while index < len(cumulative) and cumulative[index] <= sample:
                    index += 1
                if index >= len(cumulative):
                    index = len(cumulative) - 1
                if index not in new_indices:
                    new_indices.append(index)
            found.extend(new_indices)
        return [values[index] for index in found]


def _ticket(numbers: list[int]) -> tuple[int, ...]:
    values = tuple(sorted(numbers))
    if (
        len(values) != _PICK_COUNT
        or len(set(values)) != _PICK_COUNT
        or any(not _MIN_NUMBER <= number <= _MAX_NUMBER for number in values)
    ):
        raise ValueError("FROZEN_SOURCE_INVALID_TICKET")
    return values


def _target_after_causal_cutoff(history: tuple[CausalDrawRow, ...]) -> str:
    """Synthesize a target identity that is absent from causal history."""

    draw_ids = {row.draw for row in history}
    target = f"{history[-1].draw}:lottolab-wave2-next-target"
    while target in draw_ids:
        target = f"{target}:next"
    return target


def _seed_integer(target_draw_number: str) -> int:
    material = "|".join(
        (
            _HISTORY_NATIVE_WAVE2_PROTOCOL,
            _METHOD_ID,
            _SOURCE_SHA256,
            target_draw_number,
            str(_REPLICATE_ID),
            _HISTORY_NATIVE_WAVE2_DEFAULT_USER_SEED,
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return int(digest, 16)


class _CooccurrenceGraph:
    def __init__(self) -> None:
        self.edges: defaultdict[tuple[int, int], int] = defaultdict(int)

    def build(self, history: tuple[CausalDrawRow, ...]) -> None:
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
    history: tuple[CausalDrawRow, ...],
    seed_integer: int,
) -> tuple[tuple[int, ...], ...]:
    graph = _CooccurrenceGraph()
    graph.build(history)
    predictions: list[tuple[int, ...]] = []
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
                for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
                    if number not in values:
                        values.append(number)
                        break
            candidate = _ticket(values[:_PICK_COUNT])
        if candidate not in predictions:
            predictions.append(candidate)

    numpy_rng = _LegacyNumpyRandomState(seed_integer % (2**32))
    python_rng = random.Random()
    python_rng.seed(seed_integer, version=2)
    while len(predictions) < _NATIVE_TICKET_COUNT:
        if not page_rank:
            candidate = _ticket(
                python_rng.sample(range(_MIN_NUMBER, _MAX_NUMBER + 1), _PICK_COUNT)
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
    return tuple(predictions[:_NATIVE_TICKET_COUNT])


class BigLottoCooccurrenceGraphAdapter(PortfolioBetAdapter):
    """Frozen co-occurrence graph/PageRank/community portfolio adapter."""

    strategy_id = "legacy_biglotto__cooccurrence_graph__25fa2e473092"
    strategy_name = "大樂透 Cooccurrence Graph 共現圖譜 (原生最多4注)"
    strategy_version = "v0.1"
    min_history = _MINIMUM_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _NATIVE_TICKET_COUNT

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        seed_integer = _seed_integer(_target_after_causal_cutoff(history))
        return _cooccurrence_graph(history, seed_integer)


__all__ = ["BigLottoCooccurrenceGraphAdapter"]
