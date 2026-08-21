# pyright: reportPrivateUsage=false

"""Target-native port of the frozen BIG_LOTTO Cooccurrence Graph donor.

The donor is ``lottery_api/models/cooccurrence_graph.py`` at legacy commit
``49a25effa62fc24f40789c16be6f11bdfb41a4a9`` (blob
``69a7a0c903a025b4df67eaec927ecd09168e7e49``, SHA-256
``25fa2e47309232265f442a688ddc1de2bbd853ce6c63762a5298aef016c008ab``).
Its retained reference is
``legacy_history_native_portfolios_wave2._cooccurrence_graph``.

The donor's graph, ranking, candidate construction, weighted NumPy fallback,
Python fallback, uniqueness check, and duplicate-stop rule are fully retained.
Only the legacy process's module-global RNG pre-state is unavailable. This
adapter therefore injects one call-local seed into the same two RNG families:
legacy NumPy ``RandomState(MT19937)`` semantics and CPython ``random.Random``.
It imports the already-proven pure MT19937 compatibility core used by native
Anti-Consensus and adds only NumPy's weighted no-replacement choice operation.
No module-global RNG state is read or mutated.

The source promises best-effort unique output: candidates are appended in
source order until four unique tickets exist, but the first duplicate ends
generation. Its exact native cardinality is therefore one through four.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from collections.abc import Sequence
from itertools import combinations
from typing import Protocol

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import ReplayDraw, ReplayStrategy
from lottolab.strategies.adapters.base import (
    CausalDrawRow,
    InvalidOutput,
    PortfolioBetAdapter,
)
from lottolab.strategies.adapters.biglotto_anti_consensus import (
    _LegacyNumpyRandomState as _UniformLegacyNumpyRandomState,
)

_STRATEGY_ID = "legacy_biglotto__cooccurrence_graph__25fa2e473092"
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_CANDIDATE_COUNT = 20
_MAXIMUM_NATIVE_TICKET_COUNT = 4
_MINIMUM_HISTORY = 100
_DEFAULT_TARGET_SEED = 0
_MAX_RANDOM_STATE_SEED = 2**32 - 1


class _WeightedChoiceWithoutReplacementRng(Protocol):
    """The donor's NumPy fallback operation, injected in call order."""

    def choice_without_replacement(
        self,
        values: list[int],
        size: int,
        *,
        probabilities: list[float] | None = None,
    ) -> list[int]: ...


class _SampleWithoutReplacementRng(Protocol):
    """The donor's CPython fallback operation, injected in call order."""

    def sample(self, population: Sequence[int], k: int) -> list[int]: ...


class _LegacyWeightedNumpyRandomState(_UniformLegacyNumpyRandomState):
    """Extend the proven pure MT19937 seam with weighted NumPy choice.

    NumPy ``RandomState.choice(..., replace=False, p=...)`` repeatedly draws
    from the normalized cumulative probability vector, zeroing every selected
    position between passes. The retained Wave-2 reference implements this
    exact legacy operation; this target-local class deliberately does not
    translate it to CPython sampling.
    """

    def _double(self) -> float:
        first = self._next_uint32() >> 5
        second = self._next_uint32() >> 6
        return (first * 67108864.0 + second) / 9007199254740992.0

    def choice_without_replacement(
        self,
        values: list[int],
        size: int,
        *,
        probabilities: list[float] | None = None,
    ) -> list[int]:
        if probabilities is None:
            return super().choice_without_replacement(values, size)
        if size < 0 or size > len(values):
            raise ValueError("sample size is outside the population")
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
        or any(
            type(number) is not int or not _MIN_NUMBER <= number <= _MAX_NUMBER for number in values
        )
    ):
        raise InvalidOutput(f"{_STRATEGY_ID}: Cooccurrence Graph ticket is not a legal 6-of-49 set")
    return values


class _CooccurrenceGraph:
    """The donor's weighted undirected 100-draw cooccurrence graph."""

    def __init__(self) -> None:
        self.edges: defaultdict[tuple[int, int], int] = defaultdict(int)

    def build(self, history: tuple[CausalDrawRow, ...]) -> None:
        self.edges.clear()
        for draw in history[-_MINIMUM_HISTORY:]:
            for first, second in combinations(sorted(draw.numbers), 2):
                self.edges[(first, second)] += 1

    def degree_centrality(self) -> dict[int, float]:
        degrees: Counter[int] = Counter()
        for (first, second), weight in self.edges.items():
            degrees[first] += weight
            degrees[second] += weight
        maximum = max(degrees.values()) if degrees else 1
        return {number: degree / maximum for number, degree in degrees.items()}

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
            node: sum(weight for _neighbor, weight in adjacency[node]) for node in nodes
        }
        for _ in range(100):
            next_rank: dict[int, float] = {}
            for node in nodes:
                value = (1 - 0.85) / count
                for neighbor, weight in adjacency[node]:
                    outgoing = outgoing_by_node[neighbor]
                    if outgoing > 0:
                        value += 0.85 * rank[neighbor] * weight / outgoing
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


def _native_graph_candidates(
    graph: _CooccurrenceGraph,
) -> tuple[list[tuple[int, ...]], dict[int, float]]:
    """Construct donor graph-native candidates before stochastic fallback."""

    predictions: list[tuple[int, ...]] = []
    page_rank = graph.pagerank()
    if page_rank:
        top_nodes = sorted(page_rank.items(), key=lambda item: -item[1])[:_PICK_COUNT]
        predictions.append(_ticket([number for number, _ in top_nodes]))
    centrality = graph.degree_centrality()
    if centrality:
        top_nodes = sorted(centrality.items(), key=lambda item: -item[1])[:_PICK_COUNT]
        candidate = _ticket([number for number, _ in top_nodes])
        if candidate not in predictions:
            predictions.append(candidate)
    for community in sorted(graph.communities(), key=len, reverse=True)[:2]:
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
    return predictions, page_rank


def _cooccurrence_graph_tickets(
    history: tuple[CausalDrawRow, ...],
    numpy_rng: _WeightedChoiceWithoutReplacementRng,
    python_rng: _SampleWithoutReplacementRng,
) -> tuple[tuple[int, ...], ...]:
    """Run the complete donor candidate and fallback sequence."""

    graph = _CooccurrenceGraph()
    graph.build(history)
    predictions, page_rank = _native_graph_candidates(graph)

    while len(predictions) < _MAXIMUM_NATIVE_TICKET_COUNT:
        if not page_rank:
            candidate = _ticket(python_rng.sample(range(_MIN_NUMBER, _MAX_NUMBER + 1), _PICK_COUNT))
        else:
            candidates = [
                number
                for number, _score in sorted(
                    page_rank.items(),
                    key=lambda item: -item[1],
                )[:_CANDIDATE_COUNT]
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
    return tuple(predictions[:_MAXIMUM_NATIVE_TICKET_COUNT])


class BigLottoCooccurrenceGraphAdapter(PortfolioBetAdapter):
    """Explicit-seed, best-effort unique 1-4 ticket graph portfolio."""

    strategy_id = _STRATEGY_ID
    strategy_name = "大樂透 Cooccurrence Graph 共現圖譜 (原生最多4注)"
    strategy_version = "v0.1"
    min_history = _MINIMUM_HISTORY
    supported_lottery_types = (LotteryType.BIG_LOTTO,)
    native_ticket_count = _MAXIMUM_NATIVE_TICKET_COUNT
    minimum_native_ticket_count = 1
    maximum_native_ticket_count = _MAXIMUM_NATIVE_TICKET_COUNT

    def __init__(self, *, rng_seed: int = _DEFAULT_TARGET_SEED) -> None:
        if type(rng_seed) is not int or not 0 <= rng_seed <= _MAX_RANDOM_STATE_SEED:
            raise InvalidOutput(
                f"{self.strategy_id}: rng_seed must be an integer in [0..{_MAX_RANDOM_STATE_SEED}]"
            )
        self._rng_seed = rng_seed

    def with_seed(self, seed: int) -> BigLottoCooccurrenceGraphAdapter:
        """Return a call-local adapter configured with one explicit seed."""

        return BigLottoCooccurrenceGraphAdapter(rng_seed=seed)

    def expected_native_ticket_count(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> int:
        """Resolve the same seeded best-effort count through replay's count seam."""

        del strategy, target
        causal_history = tuple(
            CausalDrawRow(
                draw=draw.draw_number,
                date=draw.draw_date.isoformat(),
                numbers=draw.main_numbers,
            )
            for draw in history
        )
        return len(self.get_bets(causal_history, LotteryType.BIG_LOTTO))

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        del lottery_type
        if len({row.draw for row in history}) != len(history):
            raise InvalidOutput(f"{self.strategy_id}: causal draw identities must be unique")
        numpy_rng = _LegacyWeightedNumpyRandomState(self._rng_seed)
        python_rng = random.Random()
        python_rng.seed(self._rng_seed, version=2)
        return _cooccurrence_graph_tickets(history, numpy_rng, python_rng)


__all__ = ["BigLottoCooccurrenceGraphAdapter"]
