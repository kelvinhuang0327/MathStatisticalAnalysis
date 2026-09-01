"""Deterministic native port of the POWER_LOTTO Graph Synergy donor.

The historical donor is ``tools/power_graph_synergy.py`` (recovered exact
SHA-256 ``48701cd6854d442ced2b1ca63956d0928be23b715aaa880a116a86a8d905b581``).
Its ``power_graph_synergy`` identity remains the stochastic historical donor
authority in :mod:`.powerlotto_wave2`; this module exposes the separately
authorized deterministic variant ``power_graph_synergy_seed42_2bet``.

Graph construction, python-louvain 0.16 modularity behaviour, resolution 1.0,
community ordering, frequency ranking, ticket construction, and fallbacks are
retained. The only semantic variant is the Owner-authorized RNG boundary: each
call creates a private legacy NumPy MT19937 stream at seed 42. No process-global
NumPy state is imported, read, or mutated. The small weighted-graph and Louvain
core below is a dependency-free, typed port of the donor runtime's
``python-louvain`` 0.16 / NetworkX 3.2.1 execution path.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from itertools import combinations
from typing import Final

from lottolab.domain.draws import LotteryType
from lottolab.strategies.adapters.base import CausalDrawRow, PortfolioBetAdapter
from lottolab.strategies.adapters.biglotto_anti_consensus import (
    _LegacyNumpyRandomState,
)

_STRATEGY_ID: Final = "power_graph_synergy_seed42_2bet"
_HISTORICAL_DONOR_ID: Final = "power_graph_synergy"
_MIN_NUMBER: Final = 1
_MAX_NUMBER: Final = 38
_PICK_COUNT: Final = 6
_NATIVE_TICKET_COUNT: Final = 2
_WINDOW: Final = 500
_RESOLUTION: Final = 1.0
_CALL_LOCAL_SEED: Final = 42
_MODULARITY_EPSILON: Final = 0.0000001

_Weight = int | float


class _WeightedGraph:
    """Insertion-ordered undirected weighted graph matching NetworkX Graph."""

    def __init__(self) -> None:
        self._nodes: dict[int, None] = {}
        self._adjacency: dict[int, dict[int, _Weight]] = {}

    def add_node(self, node: int) -> None:
        if node not in self._nodes:
            self._nodes[node] = None
            self._adjacency[node] = {}

    def add_nodes_from(self, nodes: Iterable[int]) -> None:
        for node in nodes:
            self.add_node(node)

    def add_edge(self, first: int, second: int, weight: _Weight) -> None:
        self.add_node(first)
        self.add_node(second)
        self._adjacency[first][second] = weight
        self._adjacency[second][first] = weight

    def increment_edge(self, first: int, second: int) -> None:
        current = self._adjacency.get(first, {}).get(second, 0)
        self.add_edge(first, second, current + 1)

    def node_order(self) -> tuple[int, ...]:
        return tuple(self._nodes)

    def neighbors(self, node: int) -> dict[int, _Weight]:
        return self._adjacency[node]

    def edge_weight(self, first: int, second: int, default: _Weight = 0) -> _Weight:
        return self._adjacency.get(first, {}).get(second, default)

    def degree(self, node: int) -> _Weight:
        degree = sum(self._adjacency[node].values())
        if node in self._adjacency[node]:
            degree += self._adjacency[node][node]
        return degree

    def weighted_edges(self) -> tuple[tuple[int, int, _Weight], ...]:
        edges: list[tuple[int, int, _Weight]] = []
        seen: set[int] = set()
        for first in self._nodes:
            for second, weight in self._adjacency[first].items():
                if second not in seen:
                    edges.append((first, second, weight))
            seen.add(first)
        return tuple(edges)

    def total_weight(self) -> _Weight:
        return sum(weight for _first, _second, weight in self.weighted_edges())

    def copy(self) -> _WeightedGraph:
        copied = _WeightedGraph()
        copied.add_nodes_from(self._nodes)
        # NetworkX Graph.copy traverses both adjacency directions. Replaying
        # that traversal preserves its copied-neighbour insertion order.
        for first in self._nodes:
            for second, weight in self._adjacency[first].items():
                copied.add_edge(first, second, weight)
        return copied


class _LouvainStatus:
    def __init__(self) -> None:
        self.node_to_community: dict[int, int] = {}
        self.total_weight: _Weight = 0
        self.degrees: dict[int, float] = {}
        self.node_degrees: dict[int, float] = {}
        self.internals: dict[int, float] = {}
        self.loops: dict[int, float] = {}

    def initialize(self, graph: _WeightedGraph) -> None:
        self.node_to_community = {}
        self.total_weight = graph.total_weight()
        self.degrees = {}
        self.node_degrees = {}
        self.internals = {}
        for community, node in enumerate(graph.node_order()):
            self.node_to_community[node] = community
            degree = float(graph.degree(node))
            if degree < 0:
                raise ValueError(f"bad node degree: {degree}")
            self.degrees[community] = degree
            self.node_degrees[node] = degree
            loop = float(graph.edge_weight(node, node, 0))
            self.loops[node] = loop
            self.internals[community] = loop


def _randomized[T](items: Iterable[T], random_state: _LegacyNumpyRandomState) -> list[T]:
    values = list(items)
    indices = random_state.permutation(list(range(len(values))))
    return [values[index] for index in indices]


def _modularity(status: _LouvainStatus, resolution: float) -> float:
    links = float(status.total_weight)
    result = 0.0
    for community in set(status.node_to_community.values()):
        internal_degree = status.internals.get(community, 0.0)
        degree = status.degrees.get(community, 0.0)
        if links > 0:
            result += internal_degree * resolution / links - (degree / (2.0 * links)) ** 2
    return result


def _neighbor_communities(
    node: int,
    graph: _WeightedGraph,
    status: _LouvainStatus,
) -> dict[int, _Weight]:
    weights: dict[int, _Weight] = {}
    for neighbor, edge_weight in graph.neighbors(node).items():
        if neighbor != node:
            community = status.node_to_community[neighbor]
            weights[community] = weights.get(community, 0) + edge_weight
    return weights


def _remove_node(
    node: int,
    community: int,
    weight: _Weight,
    status: _LouvainStatus,
) -> None:
    status.degrees[community] = status.degrees.get(community, 0.0) - status.node_degrees.get(
        node, 0.0
    )
    status.internals[community] = float(
        status.internals.get(community, 0.0) - weight - status.loops.get(node, 0.0)
    )
    status.node_to_community[node] = -1


def _insert_node(
    node: int,
    community: int,
    weight: _Weight,
    status: _LouvainStatus,
) -> None:
    status.node_to_community[node] = community
    status.degrees[community] = status.degrees.get(community, 0.0) + status.node_degrees.get(
        node, 0.0
    )
    status.internals[community] = float(
        status.internals.get(community, 0.0) + weight + status.loops.get(node, 0.0)
    )


def _one_level(
    graph: _WeightedGraph,
    status: _LouvainStatus,
    resolution: float,
    random_state: _LegacyNumpyRandomState,
) -> None:
    modified = True
    current_modularity = _modularity(status, resolution)
    new_modularity = current_modularity
    while modified:
        current_modularity = new_modularity
        modified = False
        for node in _randomized(graph.node_order(), random_state):
            original_community = status.node_to_community[node]
            degree_weight = status.node_degrees.get(node, 0.0) / (float(status.total_weight) * 2.0)
            neighbor_communities = _neighbor_communities(node, graph, status)
            removal_cost = (
                -neighbor_communities.get(original_community, 0)
                + resolution
                * (status.degrees.get(original_community, 0.0) - status.node_degrees.get(node, 0.0))
                * degree_weight
            )
            _remove_node(
                node,
                original_community,
                neighbor_communities.get(original_community, 0),
                status,
            )
            best_community = original_community
            best_increase = 0.0
            for community, edge_weight in _randomized(neighbor_communities.items(), random_state):
                increase = (
                    removal_cost
                    + edge_weight
                    - resolution * status.degrees.get(community, 0.0) * degree_weight
                )
                if increase > best_increase:
                    best_increase = increase
                    best_community = community
            _insert_node(
                node,
                best_community,
                neighbor_communities.get(best_community, 0),
                status,
            )
            if best_community != original_community:
                modified = True
        new_modularity = _modularity(status, resolution)
        if new_modularity - current_modularity < _MODULARITY_EPSILON:
            break


def _renumber(partition: dict[int, int]) -> dict[int, int]:
    values = set(partition.values())
    target = set(range(len(values)))
    if values == target:
        return partition.copy()
    renumbering: dict[int, int] = {}
    for value in target.intersection(values):
        renumbering[value] = value
    for value, replacement in zip(
        values.difference(target),
        target.difference(values),
        strict=True,
    ):
        renumbering[value] = replacement
    return {node: renumbering[community] for node, community in partition.items()}


def _induced_graph(partition: dict[int, int], graph: _WeightedGraph) -> _WeightedGraph:
    induced = _WeightedGraph()
    induced.add_nodes_from(partition.values())
    for first, second, edge_weight in graph.weighted_edges():
        first_community = partition[first]
        second_community = partition[second]
        previous = induced.edge_weight(first_community, second_community, 0)
        induced.add_edge(first_community, second_community, previous + edge_weight)
    return induced


def _partition_at_level(
    dendrogram: list[dict[int, int]],
    level: int,
) -> dict[int, int]:
    partition = dendrogram[0].copy()
    for index in range(1, level + 1):
        for node, community in partition.items():
            partition[node] = dendrogram[index][community]
    return partition


def _best_partition(
    graph: _WeightedGraph,
    *,
    resolution: float = _RESOLUTION,
    seed: int = _CALL_LOCAL_SEED,
) -> dict[int, int]:
    """Port ``community_louvain.best_partition`` with a private seed."""

    if not graph.weighted_edges():
        return {node: community for community, node in enumerate(graph.node_order())}

    random_state = _LegacyNumpyRandomState(seed)
    current_graph = graph.copy()
    status = _LouvainStatus()
    status.initialize(current_graph)
    dendrogram: list[dict[int, int]] = []

    _one_level(current_graph, status, resolution, random_state)
    new_modularity = _modularity(status, resolution)
    partition = _renumber(status.node_to_community)
    dendrogram.append(partition)
    modularity = new_modularity
    current_graph = _induced_graph(partition, current_graph)
    status.initialize(current_graph)

    while True:
        _one_level(current_graph, status, resolution, random_state)
        new_modularity = _modularity(status, resolution)
        if new_modularity - modularity < _MODULARITY_EPSILON:
            break
        partition = _renumber(status.node_to_community)
        dendrogram.append(partition)
        modularity = new_modularity
        current_graph = _induced_graph(partition, current_graph)
        status.initialize(current_graph)

    return _partition_at_level(dendrogram, len(dendrogram) - 1)


def _build_cooccurrence_graph(
    history: tuple[CausalDrawRow, ...],
    *,
    window: int = _WINDOW,
) -> _WeightedGraph:
    graph = _WeightedGraph()
    graph.add_nodes_from(range(_MIN_NUMBER, _MAX_NUMBER + 1))
    for row in history[-window:]:
        for first, second in combinations(row.numbers, 2):
            graph.increment_edge(first, second)
    return graph


def _analyze_graph_communities(
    history: tuple[CausalDrawRow, ...],
    *,
    window: int = _WINDOW,
) -> dict[int, tuple[int, ...]]:
    graph = _build_cooccurrence_graph(history, window=window)
    partition = _best_partition(
        graph,
        resolution=_RESOLUTION,
        seed=_CALL_LOCAL_SEED,
    )
    communities: dict[int, list[int]] = {}
    for node, community in partition.items():
        communities.setdefault(community, []).append(node)
    return {community: tuple(numbers) for community, numbers in communities.items()}


def _graph_clancy_tickets(
    history: tuple[CausalDrawRow, ...],
    *,
    n_bets: int = _NATIVE_TICKET_COUNT,
    window: int = _WINDOW,
) -> tuple[tuple[int, ...], ...]:
    communities = _analyze_graph_communities(history, window=window)
    ranked_community_ids = sorted(
        communities,
        key=lambda community: len(communities[community]),
        reverse=True,
    )

    first_pool: list[int] = []
    for community in ranked_community_ids[: min(2, len(ranked_community_ids))]:
        first_pool.extend(communities[community])

    recent = history[-window:]
    frequency = Counter(number for row in recent for number in row.numbers)
    first_ranked = sorted(first_pool, key=lambda number: frequency.get(number, 0), reverse=True)
    tickets: list[tuple[int, ...]] = []
    if len(first_ranked) >= _PICK_COUNT:
        tickets.append(tuple(sorted(first_ranked[:_PICK_COUNT])))
    else:
        tickets.append(tuple(range(1, 7)))

    second_pool: list[int] = []
    for community in communities:
        members = sorted(
            communities[community],
            key=lambda number: frequency.get(number, 0),
            reverse=True,
        )
        second_pool.extend(members[:2])
    if len(second_pool) >= _PICK_COUNT:
        tickets.append(tuple(sorted(second_pool[:_PICK_COUNT])))
    else:
        tickets.append(tuple(range(7, 13)))
    return tuple(tickets[:n_bets])


class PowerLottoGraphSynergySeed42Adapter(PortfolioBetAdapter):
    """Two-ticket Louvain clan portfolio with fixed call-local seed 42."""

    strategy_id = _STRATEGY_ID
    strategy_name = "威力彩 Graph Synergy Louvain (固定種子42)"
    strategy_version = "v0.1-seed42"
    min_history = 1
    supported_lottery_types = (LotteryType.POWER_LOTTO,)
    native_ticket_count = _NATIVE_TICKET_COUNT
    call_local_seed = _CALL_LOCAL_SEED

    def _history_window(self, history: tuple[object, ...]) -> tuple[object, ...]:
        return history[-_WINDOW:]

    def _predict_all(
        self,
        history: tuple[CausalDrawRow, ...],
        lottery_type: LotteryType,
    ) -> tuple[tuple[int, ...], ...]:
        del lottery_type
        return _graph_clancy_tickets(history)


__all__ = ["PowerLottoGraphSynergySeed42Adapter"]
