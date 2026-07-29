"""Faithful port of the forty-first frozen BIG_LOTTO source-native batch."""

from __future__ import annotations

import hashlib
import heapq
from collections import Counter
from dataclasses import asdict, dataclass
from itertools import combinations, count
from typing import Final

from lottolab.application.legacy_frozen_unified_core import (
    FROZEN_CONFIG_LOADER_SHA256,
    FROZEN_PREDICTION_CONFIG_SHA256,
    FROZEN_UNIFIED_SOURCE_SHA256,
    frozen_deviation_ticket,
)
from lottolab.application.legacy_history_native_portfolios import (
    LegacyHistoryDraw,
)
from lottolab.application.strategy_preserving_20_ticket import Ticket

SOURCE_NATIVE_WAVE41_PROTOCOL = "legacy_source_native_wave41/v1"
DEFAULT_SOURCE_NATIVE_WAVE41_USER_SEED = (
    "biglotto-full-universe-source-native-wave41-v1"
)
GRAPH_METHOD_ID = "tools/backtest_graph_method.py"
SUPPORTED_SOURCE_NATIVE_WAVE41_METHODS = (GRAPH_METHOD_ID,)
SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE41_METHOD: Final = {
    GRAPH_METHOD_ID: (
        "dbc90b86f02a69575eb1c713c71d74a68c0c46ec56b80a46f0e35775f1018fbd"
    ),
}
FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE41_METHOD: Final = {
    GRAPH_METHOD_ID: (
        (
            "lottery_api/models/biglotto_graph.py",
            "4b5129659aa19628bb9d361b28ba35b65fd79f769f4bf00718c0cb7f45d62e90",
        ),
        (
            "lottery_api/models/unified_predictor.py",
            FROZEN_UNIFIED_SOURCE_SHA256,
        ),
        (
            "config/prediction_config.yaml",
            FROZEN_PREDICTION_CONFIG_SHA256,
        ),
        (
            "lottery_api/config_loader.py",
            FROZEN_CONFIG_LOADER_SHA256,
        ),
    ),
}
MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE41_METHOD: Final = {
    GRAPH_METHOD_ID: 50,
}
NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE41_METHOD: Final = {
    GRAPH_METHOD_ID: 2,
}
NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE41_METHOD: Final = {
    GRAPH_METHOD_ID: (
        "GRAPH_CENTRALITY_TICKET_THEN_UNIFIED_DEVIATION_BASELINE_TICKET"
    ),
}
SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE41_METHOD: Final = {
    GRAPH_METHOD_ID: (
        "graph_centrality",
        "unified_deviation_baseline",
    ),
}
SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE41_METHOD: Final = {
    GRAPH_METHOD_ID: 2,
}
SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE41_METHOD: Final = {
    GRAPH_METHOD_ID: "OLDEST_FIRST",
}
SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE41_METHOD: Final = {
    GRAPH_METHOD_ID: (
        "DATABASE_NEWEST_FIRST_REVERSED_TO_OLDEST_FIRST_THEN_STRICT_"
        "PREFIX_BEFORE_TARGET"
    ),
}
FROZEN_NETWORKX_SEMANTICS = (
    "NETWORKX_3_2_1_DEGREE_AND_WEIGHTED_BETWEENNESS_CENTRALITY"
)
_MIN_NUMBER = 1
_MAX_NUMBER = 49
_PICK_COUNT = 6
_GRAPH_LOOKBACK = 500


class LegacySourceNativeWave41Error(ValueError):
    """A request cannot satisfy the forty-first source-native contract."""


class LegacySourceNativeWave41SourceError(
    LegacySourceNativeWave41Error
):
    """The frozen source emitted no legal native portfolio."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave41Request:
    legacy_method_id: str
    target_draw_number: str
    history: tuple[LegacyHistoryDraw, ...]
    replicate_id: int = 0
    user_seed: str | int = DEFAULT_SOURCE_NATIVE_WAVE41_USER_SEED


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave41Metadata:
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
    source_history_order_detail: str
    graph_history_draw_count: int
    graph_node_count: int
    graph_edge_count: int
    graph_min_cooccurrence_threshold: float
    frozen_networkx_semantics: str
    graph_ranked_numbers: tuple[int, ...]
    candidate_k: None
    native_ticket_count: int
    native_ticket_count_semantics: str
    native_ticket_order: str
    native_duplicate_ticket_count: int
    combination_count: None
    source_method_combination_count: int
    combination_members: tuple[str, ...]
    frozen_support_artifacts: tuple[tuple[str, str], ...]

    def canonical_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LegacySourceNativeWave41Result:
    tickets: tuple[Ticket, ...]
    metadata: LegacySourceNativeWave41Metadata


@dataclass(frozen=True, slots=True)
class _GraphResult:
    ticket: Ticket
    ranked_numbers: tuple[int, ...]
    history_draw_count: int
    edge_count: int
    min_cooccurrence_threshold: float


def _validate_request(request: LegacySourceNativeWave41Request) -> None:
    if request.legacy_method_id not in SUPPORTED_SOURCE_NATIVE_WAVE41_METHODS:
        raise LegacySourceNativeWave41Error(
            "unsupported frozen source-native wave-41 method"
        )
    if (
        type(request.target_draw_number) is not str
        or not request.target_draw_number
        or type(request.replicate_id) is not int
        or request.replicate_id < 0
        or type(request.user_seed) not in (str, int)
    ):
        raise LegacySourceNativeWave41Error(
            "invalid frozen source-native wave-41 request"
        )
    minimum = MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE41_METHOD[
        request.legacy_method_id
    ]
    if len(request.history) < minimum:
        raise LegacySourceNativeWave41Error(
            f"method requires at least {minimum} history draws"
        )
    seen: set[str] = set()
    for draw in request.history:
        if (
            not draw.draw_number
            or draw.draw_number == request.target_draw_number
            or draw.draw_number in seen
            or len(draw.numbers) != _PICK_COUNT
            or len(set(draw.numbers)) != _PICK_COUNT
            or any(
                type(number) is not int
                or not _MIN_NUMBER <= number <= _MAX_NUMBER
                for number in draw.numbers
            )
        ):
            raise LegacySourceNativeWave41Error(
                "causal history draw identities are invalid"
            )
        seen.add(draw.draw_number)


def _seed(
    request: LegacySourceNativeWave41Request,
) -> tuple[str, str, int]:
    material = "|".join(
        (
            SOURCE_NATIVE_WAVE41_PROTOCOL,
            request.legacy_method_id,
            SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE41_METHOD[
                request.legacy_method_id
            ],
            request.target_draw_number,
            str(request.replicate_id),
            str(request.user_seed),
        )
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return material, digest, int(digest, 16)


def _graph_edges(
    history: tuple[LegacyHistoryDraw, ...],
) -> tuple[
    tuple[LegacyHistoryDraw, ...],
    dict[int, dict[int, float]],
    Counter[int],
    dict[int, int],
    float,
]:
    recent = (
        history[-_GRAPH_LOOKBACK:]
        if len(history) > _GRAPH_LOOKBACK
        else history
    )
    frequency: Counter[int] = Counter()
    pair_frequency: Counter[tuple[int, int]] = Counter()
    for draw in recent:
        frequency.update(draw.numbers)
        for pair in combinations(sorted(draw.numbers), 2):
            pair_frequency[pair] += 1
    last_seen: dict[int, int] = {}
    for age, draw in enumerate(reversed(recent)):
        for number in draw.numbers:
            if number not in last_seen:
                last_seen[number] = age
    threshold = max(2, len(recent) * 0.01)
    adjacency: dict[int, dict[int, float]] = {
        number: {} for number in range(_MIN_NUMBER, _MAX_NUMBER + 1)
    }
    for (left, right), pair_count in pair_frequency.items():
        if pair_count >= threshold:
            weight = pair_count / len(recent)
            adjacency[left][right] = weight
            adjacency[right][left] = weight
    return recent, adjacency, frequency, last_seen, threshold


def _weighted_betweenness(
    adjacency: dict[int, dict[int, float]],
) -> dict[int, float]:
    nodes = tuple(adjacency)
    centrality = dict.fromkeys(nodes, 0.0)
    for source in nodes:
        stack: list[int] = []
        predecessors: dict[int, list[int]] = {
            node: [] for node in nodes
        }
        sigma = dict.fromkeys(nodes, 0.0)
        distances: dict[int, float] = {}
        sigma[source] = 1.0
        seen: dict[int, float] = {source: 0.0}
        sequence = count()
        queue: list[tuple[float, int, int, int]] = []
        heapq.heappush(
            queue,
            (0.0, next(sequence), source, source),
        )
        while queue:
            distance, _sequence_id, predecessor, node = heapq.heappop(
                queue
            )
            if node in distances:
                continue
            sigma[node] += sigma[predecessor]
            stack.append(node)
            distances[node] = distance
            for neighbor, weight in adjacency[node].items():
                candidate_distance = distance + weight
                if neighbor not in distances and (
                    neighbor not in seen
                    or candidate_distance < seen[neighbor]
                ):
                    seen[neighbor] = candidate_distance
                    heapq.heappush(
                        queue,
                        (
                            candidate_distance,
                            next(sequence),
                            node,
                            neighbor,
                        ),
                    )
                    sigma[neighbor] = 0.0
                    predecessors[neighbor] = [node]
                elif candidate_distance == seen[neighbor]:
                    sigma[neighbor] += sigma[node]
                    predecessors[neighbor].append(node)
        dependency = dict.fromkeys(stack, 0.0)
        while stack:
            node = stack.pop()
            coefficient = (1.0 + dependency[node]) / sigma[node]
            for predecessor in predecessors[node]:
                dependency[predecessor] += (
                    sigma[predecessor] * coefficient
                )
            if node != source:
                centrality[node] += dependency[node]
    scale = 1.0 / ((len(nodes) - 1) * (len(nodes) - 2))
    return {
        node: value * scale for node, value in centrality.items()
    }


def _graph_ticket(
    history: tuple[LegacyHistoryDraw, ...],
) -> _GraphResult:
    recent, adjacency, frequency, last_seen, threshold = _graph_edges(
        history
    )
    betweenness = _weighted_betweenness(adjacency)
    recent_30 = recent[-30:] if len(recent) > 30 else recent
    scores: dict[int, float] = {}
    for number in range(_MIN_NUMBER, _MAX_NUMBER + 1):
        hot_score = sum(
            1 for draw in recent_30 if number in draw.numbers
        )
        frequency_ratio = frequency.get(number, 0) / len(recent)
        degree_centrality = len(adjacency[number]) / (_MAX_NUMBER - 1)
        recency = last_seen.get(number, len(recent))
        scores[number] = (
            degree_centrality * 2.0
            + betweenness[number] * 1.5
            + frequency_ratio * 1.5
            + (1.0 if hot_score >= 5 else 0.0) * 0.8
            - (0.5 if recency >= 15 else 0.0) * 0.3
        )
    ranked = tuple(
        number
        for number, _score in sorted(
            scores.items(),
            key=lambda item: -item[1],
        )
    )
    ticket = tuple(sorted(ranked[:_PICK_COUNT]))
    if len(ticket) != _PICK_COUNT:
        raise LegacySourceNativeWave41SourceError(
            "FROZEN_SOURCE_INVALID_GRAPH_TICKET"
        )
    return _GraphResult(
        ticket=ticket,
        ranked_numbers=ranked,
        history_draw_count=len(recent),
        edge_count=sum(len(neighbors) for neighbors in adjacency.values())
        // 2,
        min_cooccurrence_threshold=threshold,
    )


def generate_legacy_source_native_wave41_portfolio(
    request: LegacySourceNativeWave41Request,
) -> LegacySourceNativeWave41Result:
    """Reproduce graph centrality then deviation baseline source order."""

    _validate_request(request)
    seed_material, seed_digest, seed_integer = _seed(request)
    graph = _graph_ticket(request.history)
    tickets = (
        graph.ticket,
        frozen_deviation_ticket(request.history),
    )
    return LegacySourceNativeWave41Result(
        tickets=tickets,
        metadata=LegacySourceNativeWave41Metadata(
            protocol=SOURCE_NATIVE_WAVE41_PROTOCOL,
            legacy_method_id=request.legacy_method_id,
            source_sha256=(
                SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE41_METHOD[
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
            source_history_order=(
                SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE41_METHOD[
                    request.legacy_method_id
                ]
            ),
            source_history_order_detail=(
                SOURCE_HISTORY_ORDER_DETAIL_BY_SOURCE_NATIVE_WAVE41_METHOD[
                    request.legacy_method_id
                ]
            ),
            graph_history_draw_count=graph.history_draw_count,
            graph_node_count=49,
            graph_edge_count=graph.edge_count,
            graph_min_cooccurrence_threshold=(
                graph.min_cooccurrence_threshold
            ),
            frozen_networkx_semantics=FROZEN_NETWORKX_SEMANTICS,
            graph_ranked_numbers=graph.ranked_numbers,
            candidate_k=None,
            native_ticket_count=len(tickets),
            native_ticket_count_semantics=(
                NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE41_METHOD[
                    request.legacy_method_id
                ]
            ),
            native_ticket_order=(
                "GRAPH_CENTRALITY_THEN_DEVIATION_BASELINE_SOURCE_ORDER"
            ),
            native_duplicate_ticket_count=(
                len(tickets) - len(set(tickets))
            ),
            combination_count=None,
            source_method_combination_count=(
                SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE41_METHOD[
                    request.legacy_method_id
                ]
            ),
            combination_members=(
                SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE41_METHOD[
                    request.legacy_method_id
                ]
            ),
            frozen_support_artifacts=(
                FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE41_METHOD[
                    request.legacy_method_id
                ]
            ),
        ),
    )


__all__ = [
    "DEFAULT_SOURCE_NATIVE_WAVE41_USER_SEED",
    "FROZEN_NETWORKX_SEMANTICS",
    "FROZEN_SUPPORT_ARTIFACTS_BY_SOURCE_NATIVE_WAVE41_METHOD",
    "GRAPH_METHOD_ID",
    "MINIMUM_HISTORY_BY_SOURCE_NATIVE_WAVE41_METHOD",
    "NATIVE_TICKET_COUNT_BY_SOURCE_NATIVE_WAVE41_METHOD",
    "NATIVE_TICKET_SEMANTICS_BY_SOURCE_NATIVE_WAVE41_METHOD",
    "SOURCE_COMBINATION_COUNT_BY_SOURCE_NATIVE_WAVE41_METHOD",
    "SOURCE_COMBINATION_MEMBERS_BY_SOURCE_NATIVE_WAVE41_METHOD",
    "SOURCE_HISTORY_ORDER_BY_SOURCE_NATIVE_WAVE41_METHOD",
    "SOURCE_NATIVE_WAVE41_PROTOCOL",
    "SOURCE_SHA256_BY_SOURCE_NATIVE_WAVE41_METHOD",
    "SUPPORTED_SOURCE_NATIVE_WAVE41_METHODS",
    "LegacySourceNativeWave41Error",
    "LegacySourceNativeWave41Metadata",
    "LegacySourceNativeWave41Request",
    "LegacySourceNativeWave41Result",
    "LegacySourceNativeWave41SourceError",
    "generate_legacy_source_native_wave41_portfolio",
]
