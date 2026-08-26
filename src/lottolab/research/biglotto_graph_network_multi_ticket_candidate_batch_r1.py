"""Causal BigLotto multiscale graph/PageRank candidate batch R1.

This module freezes one exact, history-only source-ticket universe.  Each of
the three preregistered windows builds an integer same-draw co-occurrence
graph over all 49 numbers, applies a fixed 20-step rational PageRank, and
contributes an equal rank to the fused top-number pool.  The resulting 210
ordered source tickets are passed directly to the three frozen portfolio
constructors at their native 5, 10, and 20 ticket budgets.

The producer has no outcome access, fitted parameters, I/O, randomness, or
production catalog registration.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations, islice
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import biglotto_multi_ticket_constructors_r1 as _constructors

type Ticket = tuple[int, int, int, int, int, int]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type EdgeMatrix = tuple[tuple[int, ...], ...]
type RationalRanks = tuple[Fraction, ...]
type TicketPortfolio = tuple[Ticket, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
SOURCE_UNIVERSE_ID: Final[str] = "B649_MULTISCALE_GRAPH_PAGERANK_RANKED_POOL_V1"
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"
METHOD_FAMILY: Final[str] = "GRAPH"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
GRAPH_NODE_DOMAIN: Final[tuple[int, int]] = NUMBER_DOMAIN
GRAPH_NODE_COUNT: Final[int] = 49
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
SOURCE_WINDOWS: Final[tuple[int, int, int]] = WINDOWS
MINIMUM_HISTORY: Final[int] = 750
TOP_NUMBER_COUNT: Final[int] = 10
SOURCE_CANDIDATE_TICKET_COUNT: Final[int] = 210
SOURCE_TICKET_ORDER: Final[str] = "LEXICOGRAPHIC_RANK_POSITION_COMBINATION_ORDER"

EDGE_DEFINITION: Final[str] = (
    "UNDIRECTED_EDGE_W(a,b)=COUNT_WINDOW_DRAWS_CONTAINING_BOTH;a<b"
)
EDGE_WEIGHT_RULE: Final[str] = "UNDECAYED_INTEGER_SAME_DRAW_COOCCURRENCE"
PAGERANK_DAMPING: Final[Fraction] = Fraction(17, 20)
PAGERANK_ITERATIONS: Final[int] = 20
PAGERANK_INITIALIZATION: Final[str] = "UNIFORM_1_OVER_49"
PAGERANK_DANGLING_RULE: Final[str] = "UNIFORM_REDISTRIBUTION"
PAGERANK_ARITHMETIC: Final[str] = "EXACT_RATIONAL"
PER_WINDOW_RANKING_RULE: Final[str] = "PAGERANK_DESCENDING_NUMBER_ASCENDING"
WINDOW_NORMALIZATION_RULE: Final[str] = "NORMALIZED=(49-POSITION)/48;EXACT_RATIONAL"
WINDOW_FUSION_RULE: Final[str] = (
    "EQUAL_RANK_AGGREGATION;MEAN=(NORMALIZED_50+NORMALIZED_300+NORMALIZED_750)/3"
)
ROBUSTNESS_RULE: Final[str] = "SORTED_ASCENDING=(MINIMUM,MEDIAN,MAXIMUM)"
CAUSAL_CUTOFF_RULE: Final[str] = "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
PARAMETER_SELECTION_RULE: Final[str] = "FIXED_PREREGISTERED_NO_OUTCOME_TUNING"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = "MULTISCALE_NETWORK_CENTRALITY_STRUCTURE"

CONSTRUCTOR_IDS: Final[tuple[str, str, str]] = (
    "B649_CANDIDATE_SET_LOW_OVERLAP_V1",
    "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
    "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1",
)
TICKET_COUNTS: Final[tuple[int, int, int]] = (5, 10, 20)

_CONSTRUCTOR_SYMBOL_SLUGS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "low_overlap",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "exposure_balanced",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": "hybrid_diversity",
    }
)
_CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "TICKET_PAIRWISE_DIVERSITY",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "NUMBER_EXPOSURE_DIVERSITY",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": (
            "PAIRWISE_AND_NUMBER_EXPOSURE_DIVERSITY"
        ),
    }
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the preregistered 750 prior draws are available."""


@dataclass(frozen=True, slots=True)
class SourceUniverseMetadata:
    """Immutable authority metadata for the graph source universe."""

    SOURCE_UNIVERSE_ID: str
    VERSION: str
    METHOD_FAMILY: str
    LOTTERY_TYPE: str
    PICK_COUNT: int
    NUMBER_DOMAIN: tuple[int, int]
    WINDOWS: tuple[int, int, int]
    MINIMUM_HISTORY: int
    GRAPH_NODE_DOMAIN: tuple[int, int]
    EDGE_DEFINITION: str
    EDGE_WEIGHT_RULE: str
    PAGERANK_DAMPING: str
    PAGERANK_ITERATIONS: int
    PAGERANK_INITIALIZATION: str
    PAGERANK_DANGLING_RULE: str
    PAGERANK_ARITHMETIC: str
    PER_WINDOW_RANKING_RULE: str
    WINDOW_NORMALIZATION_RULE: str
    WINDOW_FUSION_RULE: str
    ROBUSTNESS_RULE: str
    TOP_NUMBER_COUNT: int
    SOURCE_CANDIDATE_TICKET_COUNT: int
    SOURCE_TICKET_ORDER: str
    RNG_SEMANTICS: str


SOURCE_UNIVERSE_METADATA: Final[SourceUniverseMetadata] = SourceUniverseMetadata(
    SOURCE_UNIVERSE_ID=SOURCE_UNIVERSE_ID,
    VERSION=SOURCE_UNIVERSE_VERSION,
    METHOD_FAMILY=METHOD_FAMILY,
    LOTTERY_TYPE=LOTTERY_TYPE,
    PICK_COUNT=PICK_COUNT,
    NUMBER_DOMAIN=NUMBER_DOMAIN,
    WINDOWS=WINDOWS,
    MINIMUM_HISTORY=MINIMUM_HISTORY,
    GRAPH_NODE_DOMAIN=GRAPH_NODE_DOMAIN,
    EDGE_DEFINITION=EDGE_DEFINITION,
    EDGE_WEIGHT_RULE=EDGE_WEIGHT_RULE,
    PAGERANK_DAMPING="17/20",
    PAGERANK_ITERATIONS=PAGERANK_ITERATIONS,
    PAGERANK_INITIALIZATION=PAGERANK_INITIALIZATION,
    PAGERANK_DANGLING_RULE=PAGERANK_DANGLING_RULE,
    PAGERANK_ARITHMETIC=PAGERANK_ARITHMETIC,
    PER_WINDOW_RANKING_RULE=PER_WINDOW_RANKING_RULE,
    WINDOW_NORMALIZATION_RULE=WINDOW_NORMALIZATION_RULE,
    WINDOW_FUSION_RULE=WINDOW_FUSION_RULE,
    ROBUSTNESS_RULE=ROBUSTNESS_RULE,
    TOP_NUMBER_COUNT=TOP_NUMBER_COUNT,
    SOURCE_CANDIDATE_TICKET_COUNT=SOURCE_CANDIDATE_TICKET_COUNT,
    SOURCE_TICKET_ORDER=SOURCE_TICKET_ORDER,
    RNG_SEMANTICS=RNG_SEMANTICS,
)

SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = MappingProxyType(
    {
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "METHOD_FAMILY": METHOD_FAMILY,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "PICK_COUNT": PICK_COUNT,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "HISTORY_ORDER": HISTORY_ORDER,
        "WINDOWS": WINDOWS,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "GRAPH_NODE_DOMAIN": GRAPH_NODE_DOMAIN,
        "EDGE_DEFINITION": EDGE_DEFINITION,
        "EDGE_WEIGHT_RULE": EDGE_WEIGHT_RULE,
        "PAGERANK_DAMPING": "17/20",
        "PAGERANK_ITERATIONS": PAGERANK_ITERATIONS,
        "PAGERANK_INITIALIZATION": PAGERANK_INITIALIZATION,
        "PAGERANK_DANGLING_RULE": PAGERANK_DANGLING_RULE,
        "PAGERANK_ARITHMETIC": PAGERANK_ARITHMETIC,
        "PER_WINDOW_RANKING_RULE": PER_WINDOW_RANKING_RULE,
        "WINDOW_NORMALIZATION_RULE": WINDOW_NORMALIZATION_RULE,
        "WINDOW_FUSION_RULE": WINDOW_FUSION_RULE,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "RNG_SEMANTICS": RNG_SEMANTICS,
    }
)


@dataclass(frozen=True, slots=True)
class GraphWindow:
    """Exact graph, PageRank, and rank-order details for one window."""

    WINDOW: int
    EDGE_COUNTS: EdgeMatrix
    NODE_STRENGTHS: tuple[int, ...]
    PAGERANKS: RationalRanks
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: RationalRanks

    @property
    def EDGE_MATRIX(self) -> EdgeMatrix:
        """Compatibility name for the immutable edge-count matrix."""

        return self.EDGE_COUNTS

    @property
    def STRENGTHS(self) -> tuple[int, ...]:
        """Compatibility name for exact integer node strengths."""

        return self.NODE_STRENGTHS

    @property
    def RANKS(self) -> RationalRanks:
        """Compatibility name for the final exact PageRank vector."""

        return self.PAGERANKS

    def edge(self, left: int, right: int) -> int:
        _validate_number(left)
        _validate_number(right)
        return self.EDGE_COUNTS[left - 1][right - 1]

    def strength(self, number: int) -> int:
        _validate_number(number)
        return self.NODE_STRENGTHS[number - 1]

    def pagerank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.PAGERANKS[number - 1]

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]


# Prior source modules use WindowRanking as the public per-window result name.
WindowRanking = GraphWindow


@dataclass(frozen=True, slots=True)
class FusedNumberRanking:
    """Three-window fusion with exact rank means and robustness values."""

    ORDERED_NUMBERS: tuple[int, ...]
    MEAN_RANKS: RationalRanks
    ROBUSTNESS: tuple[tuple[Fraction, Fraction, Fraction], ...]
    WINDOW_RANKINGS: tuple[GraphWindow, ...]

    @property
    def TOP_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS[:TOP_NUMBER_COUNT]

    def mean_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.MEAN_RANKS[number - 1]

    def robustness(self, number: int) -> tuple[Fraction, Fraction, Fraction]:
        _validate_number(number)
        return self.ROBUSTNESS[number - 1]


def _validate_number(number: int) -> None:
    if type(number) is not int or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]:
        raise ValueError(f"number must be an integer in {NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}")


def _validate_target_index(target_index: int) -> None:
    if type(target_index) is not int or target_index < 0:
        raise ValueError("target_index must be a non-negative integer")


def _read_history_prefix(history: HistoryInput, target_index: int) -> tuple[object, ...]:
    _validate_target_index(target_index)
    try:
        if isinstance(history, Sequence):
            if target_index > len(history):
                raise ValueError("target_index must not exceed history length")
            return tuple(history[:target_index])

        prefix = tuple(islice(iter(history), target_index))
        if len(prefix) != target_index:
            raise ValueError("target_index must not exceed history length")
        return prefix
    except ValueError:
        raise
    except (TypeError, IndexError) as error:
        raise ValueError("history must be a finite chronological sequence of draws") from error


def _validate_draw(raw_draw: object, draw_index: int) -> HistoryDraw:
    try:
        values: tuple[object, ...] = tuple(cast(Iterable[object], raw_draw))
    except TypeError as error:
        raise ValueError(f"history[{draw_index}] must contain exactly six integers") from error

    if len(values) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain exactly {PICK_COUNT} numbers")

    numbers: list[int] = []
    for position, raw_number in enumerate(values):
        if type(raw_number) is not int:
            raise ValueError(f"history[{draw_index}][{position}] must be an integer")
        if not NUMBER_DOMAIN[0] <= raw_number <= NUMBER_DOMAIN[1]:
            raise ValueError(
                f"history[{draw_index}][{position}] must be in "
                f"{NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}"
            )
        numbers.append(raw_number)

    if len(set(numbers)) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain six unique numbers")
    return cast(HistoryDraw, tuple(numbers))


def validate_prior_history(history: HistoryInput, target_index: int) -> tuple[HistoryDraw, ...]:
    """Return an immutable copy of only the strictly prior validated history."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    return tuple(_validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix))


def _validate_window(window: int) -> None:
    if type(window) is not int or window not in WINDOWS:
        raise ValueError(f"window must be one of {WINDOWS}")


def _validate_edge_matrix(raw_edge_counts: Sequence[Sequence[object]]) -> EdgeMatrix:
    if len(raw_edge_counts) != GRAPH_NODE_COUNT:
        raise ValueError(f"edge_counts must contain exactly {GRAPH_NODE_COUNT} rows")

    rows: list[tuple[int, ...]] = []
    for row_index, raw_row in enumerate(raw_edge_counts):
        if len(raw_row) != GRAPH_NODE_COUNT:
            raise ValueError(
                f"edge_counts[{row_index}] must contain exactly {GRAPH_NODE_COUNT} columns"
            )
        row: list[int] = []
        for column_index, raw_value in enumerate(raw_row):
            if type(raw_value) is not int or raw_value < 0:
                raise ValueError(
                    f"edge_counts[{row_index}][{column_index}] must be a non-negative integer"
                )
            row.append(raw_value)
        rows.append(tuple(row))

    matrix = tuple(rows)
    for number in range(GRAPH_NODE_COUNT):
        if matrix[number][number] != 0:
            raise ValueError("edge_counts must have zero self-edges")
        for other in range(number + 1, GRAPH_NODE_COUNT):
            if matrix[number][other] != matrix[other][number]:
                raise ValueError("edge_counts must be symmetric")
    return matrix


def _node_strengths(edge_counts: EdgeMatrix) -> tuple[int, ...]:
    return tuple(sum(row) for row in edge_counts)


def _validate_strengths(
    edge_counts: EdgeMatrix, raw_strengths: Sequence[object] | None
) -> tuple[int, ...]:
    strengths = _node_strengths(edge_counts) if raw_strengths is None else tuple(raw_strengths)
    if len(strengths) != GRAPH_NODE_COUNT:
        raise ValueError(f"node_strengths must contain exactly {GRAPH_NODE_COUNT} values")
    for index, strength in enumerate(strengths):
        if type(strength) is not int or strength < 0:
            raise ValueError(f"node_strengths[{index}] must be a non-negative integer")
    if tuple(strengths) != _node_strengths(edge_counts):
        raise ValueError("node_strengths must equal the exact edge-row sums")
    return cast(tuple[int, ...], strengths)


def build_cooccurrence_edge_counts(
    draws: Iterable[HistoryDraw],
) -> EdgeMatrix:
    """Build the fixed 49-node integer same-draw co-occurrence matrix."""

    mutable_edges = [[0] * GRAPH_NODE_COUNT for _ in range(GRAPH_NODE_COUNT)]
    draw_count = 0
    for draw_count, raw_draw in enumerate(draws, start=1):
        draw = _validate_draw(raw_draw, draw_count - 1)
        for left, right in combinations(sorted(draw), 2):
            left_index = left - 1
            right_index = right - 1
            mutable_edges[left_index][right_index] += 1
            mutable_edges[right_index][left_index] += 1

    edge_counts = _validate_edge_matrix(tuple(tuple(row) for row in mutable_edges))
    if sum(map(sum, edge_counts)) != draw_count * 2 * (PICK_COUNT * (PICK_COUNT - 1) // 2):
        raise RuntimeError("each historical draw must contribute exactly 15 unordered edges")
    return edge_counts


def _validate_page_rank_state(ranks: RationalRanks) -> None:
    if len(ranks) != GRAPH_NODE_COUNT:
        raise RuntimeError("PageRank state has the wrong node count")
    if any(rank < 0 for rank in ranks):
        raise RuntimeError("PageRank state contains a negative rank")
    if sum(ranks, Fraction(0, 1)) != Fraction(1, 1):
        raise RuntimeError("PageRank state does not sum to one exactly")


def calculate_page_rank(
    edge_counts: Sequence[Sequence[object]],
    node_strengths: Sequence[object] | None = None,
) -> RationalRanks:
    """Run exactly 20 iterations of exact-rational dangling-node PageRank."""

    matrix = _validate_edge_matrix(edge_counts)
    strengths = _validate_strengths(matrix, node_strengths)
    ranks: RationalRanks = tuple(
        Fraction(1, GRAPH_NODE_COUNT) for _ in range(GRAPH_NODE_COUNT)
    )
    _validate_page_rank_state(ranks)
    teleport = (Fraction(1, 1) - PAGERANK_DAMPING) / GRAPH_NODE_COUNT

    for _ in range(PAGERANK_ITERATIONS):
        dangling_mass = sum(
            (ranks[index] for index, strength in enumerate(strengths) if strength == 0),
            Fraction(0, 1),
        )
        next_ranks: list[Fraction] = []
        for target_index in range(GRAPH_NODE_COUNT):
            incoming = sum(
                (
                    ranks[source_index]
                    * matrix[source_index][target_index]
                    / strengths[source_index]
                    for source_index, strength in enumerate(strengths)
                    if strength > 0 and source_index != target_index
                ),
                Fraction(0, 1),
            )
            next_ranks.append(
                teleport
                + PAGERANK_DAMPING
                * (incoming + dangling_mass / GRAPH_NODE_COUNT)
            )
        ranks = tuple(next_ranks)
        _validate_page_rank_state(ranks)

    return ranks


exact_pagerank = calculate_page_rank
calculate_exact_pagerank = calculate_page_rank


def _rank_graph(
    window: int,
    edge_counts: EdgeMatrix,
    strengths: tuple[int, ...],
    ranks: RationalRanks,
) -> GraphWindow:
    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-ranks[number - 1], number),
        )
    )
    positions = [0] * GRAPH_NODE_COUNT
    normalized_ranks: list[Fraction] = [Fraction(0, 1)] * GRAPH_NODE_COUNT
    for position, number in enumerate(ordered_numbers, start=1):
        positions[number - 1] = position
        normalized_ranks[number - 1] = Fraction(
            GRAPH_NODE_COUNT - position, GRAPH_NODE_COUNT - 1
        )
    return GraphWindow(
        WINDOW=window,
        EDGE_COUNTS=edge_counts,
        NODE_STRENGTHS=strengths,
        PAGERANKS=ranks,
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized_ranks),
    )


def _build_validated_graph_window(
    prior_history: tuple[HistoryDraw, ...], window: int
) -> GraphWindow:
    _validate_window(window)
    if len(prior_history) < window:
        raise InsufficientHistoryError(f"window {window} requires at least {window} prior draws")
    edge_counts = build_cooccurrence_edge_counts(prior_history[-window:])
    strengths = _node_strengths(edge_counts)
    ranks = calculate_page_rank(edge_counts, strengths)
    return _rank_graph(window, edge_counts, strengths, ranks)


def build_graph_for_window(
    history: HistoryInput, target_index: int, window: int
) -> GraphWindow:
    """Build one exact graph and ranking from the strictly prior history."""

    prior_history = validate_prior_history(history, target_index)
    return _build_validated_graph_window(prior_history, window)


build_cooccurrence_graph = build_graph_for_window
calculate_graph_for_window = build_graph_for_window
rank_numbers_by_window = build_graph_for_window


def raw_frequency_order_for_window(
    history: HistoryInput, target_index: int, window: int
) -> tuple[int, ...]:
    """Return the raw frequency order used only for graph-specificity checks."""

    prior_history = validate_prior_history(history, target_index)
    _validate_window(window)
    if len(prior_history) < window:
        raise InsufficientHistoryError(f"window {window} requires at least {window} prior draws")
    frequencies = [0] * GRAPH_NODE_COUNT
    for draw in prior_history[-window:]:
        for number in draw:
            frequencies[number - 1] += 1
    return tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-frequencies[number - 1], number),
        )
    )


def calculate_window_rankings(
    history: HistoryInput, target_index: int
) -> tuple[GraphWindow, GraphWindow, GraphWindow]:
    """Calculate the exact 50/300/750 graph rankings."""

    prior_history = validate_prior_history(history, target_index)
    rankings = tuple(
        _build_validated_graph_window(prior_history, window) for window in WINDOWS
    )
    return cast(tuple[GraphWindow, GraphWindow, GraphWindow], rankings)


calculate_graph_rankings = calculate_window_rankings


def fuse_window_rankings(
    window_rankings: Sequence[GraphWindow],
) -> FusedNumberRanking:
    """Fuse three window rankings with equal exact rational rank aggregation."""

    if tuple(ranking.WINDOW for ranking in window_rankings) != WINDOWS:
        raise ValueError(f"window_rankings must contain windows in order {WINDOWS}")

    mean_ranks: list[Fraction] = []
    robustness: list[tuple[Fraction, Fraction, Fraction]] = []
    for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1):
        normalized = tuple(ranking.normalized_rank(number) for ranking in window_rankings)
        mean_ranks.append(sum(normalized, Fraction(0, 1)) / len(normalized))
        sorted_ranks = tuple(sorted(normalized))
        robustness.append(cast(tuple[Fraction, Fraction, Fraction], sorted_ranks))

    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (
                -mean_ranks[number - 1],
                -robustness[number - 1][0],
                -robustness[number - 1][1],
                -robustness[number - 1][2],
                number,
            ),
        )
    )
    return FusedNumberRanking(
        ORDERED_NUMBERS=ordered_numbers,
        MEAN_RANKS=tuple(mean_ranks),
        ROBUSTNESS=tuple(robustness),
        WINDOW_RANKINGS=tuple(window_rankings),
    )


def calculate_fused_number_ranking(
    history: HistoryInput, target_index: int
) -> FusedNumberRanking:
    """Calculate the final fused graph-number ranking from prior history only."""

    return fuse_window_rankings(calculate_window_rankings(history, target_index))


def produce_b649_multiscale_graph_pagerank_ranked_pool_v1(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce the ordered 210-ticket graph source universe."""

    fused_ranking = calculate_fused_number_ranking(history, target_index)
    top_numbers = fused_ranking.TOP_NUMBERS
    if len(top_numbers) != TOP_NUMBER_COUNT:
        raise RuntimeError("fused ranking did not produce the configured top-number pool")

    tickets: list[Ticket] = []
    for rank_positions in combinations(range(TOP_NUMBER_COUNT), PICK_COUNT):
        ticket = cast(Ticket, tuple(sorted(top_numbers[position] for position in rank_positions)))
        tickets.append(ticket)

    source_tickets = tuple(tickets)
    if len(source_tickets) != SOURCE_CANDIDATE_TICKET_COUNT:
        raise RuntimeError("source universe did not produce exactly 210 tickets")
    if len(set(source_tickets)) != len(source_tickets):
        raise RuntimeError("source universe produced duplicate tickets")
    return source_tickets


produce_source_ticket_universe = produce_b649_multiscale_graph_pagerank_ranked_pool_v1
build_source_ticket_universe = produce_b649_multiscale_graph_pagerank_ranked_pool_v1


def _json_ready(value: object) -> object:
    if isinstance(value, Mapping):
        converted: dict[str, object] = {}
        mapping = cast(Mapping[object, object], value)
        for key, item in mapping.items():
            if not isinstance(key, str):
                raise TypeError("semantic-record keys must be strings")
            converted[key] = _json_ready(item)
        return converted
    if isinstance(value, tuple):
        return [_json_ready(item) for item in cast(tuple[object, ...], value)]
    if isinstance(value, list):
        return [_json_ready(item) for item in cast(list[object], value)]
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    return value


def canonicalize_semantic_record(record: object) -> bytes:
    """Return sorted-key, compact UTF-8 JSON for a complete semantic record."""

    if not isinstance(record, Mapping):
        raise TypeError("semantic record must be a mapping")
    json_ready_record = _json_ready(cast(Mapping[object, object], record))
    return json.dumps(
        json_ready_record,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_semantic_json(record: Mapping[str, object]) -> str:
    """Return the canonical semantic JSON as text."""

    return canonicalize_semantic_record(record).decode("utf-8")


def signature_hash_for_semantics(record: Mapping[str, object]) -> str:
    """Return the SHA-256 hash of canonical semantic JSON."""

    return hashlib.sha256(canonicalize_semantic_record(record)).hexdigest()


def candidate_id_for_semantics(record: Mapping[str, object]) -> str:
    """Derive the frozen graph candidate ID from a semantic record."""

    return f"BMSGV1_GR_{signature_hash_for_semantics(record)[:16]}"


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """Deterministic identity material for one graph hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    """Derive candidate ID and full signature hash together."""

    canonical_json = canonical_semantic_json(record)
    signature_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return CandidateIdentity(
        CANDIDATE_ID=f"BMSGV1_GR_{signature_hash[:16]}",
        SIGNATURE_HASH=signature_hash,
        CANONICAL_SEMANTIC_JSON=canonical_json,
    )


@dataclass(frozen=True, slots=True)
class CandidateMetadata:
    """Immutable authority metadata for one graph research hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    SEMANTICS: Mapping[str, object]
    CONSTRUCTOR_ID: str
    TICKET_COUNT: int
    IMPLEMENTATION_SYMBOL: str


def _implementation_symbol(constructor_id: str, ticket_count: int) -> str:
    return (
        "produce_b649_graph_network_multiticket_"
        f"{_CONSTRUCTOR_SYMBOL_SLUGS[constructor_id]}_v1_k{ticket_count}"
    )


def _candidate_semantic_record(constructor_id: str, ticket_count: int) -> dict[str, object]:
    constructor_metadata = _constructors.CONSTRUCTOR_METADATA[constructor_id]
    return {
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "CONSTRUCTOR_ID": constructor_id,
        "CONSTRUCTOR_VERSION": constructor_metadata.VERSION,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EDGE_DEFINITION": EDGE_DEFINITION,
        "EDGE_WEIGHT_RULE": EDGE_WEIGHT_RULE,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NATIVE_TICKET_COUNT": ticket_count,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "OUTPUT_SHAPE": OUTPUT_SHAPE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PAGERANK_ARITHMETIC": PAGERANK_ARITHMETIC,
        "PAGERANK_DAMPING": "17/20",
        "PAGERANK_DANGLING_RULE": PAGERANK_DANGLING_RULE,
        "PAGERANK_INITIALIZATION": PAGERANK_INITIALIZATION,
        "PAGERANK_ITERATIONS": PAGERANK_ITERATIONS,
        "PER_WINDOW_RANKING_RULE": PER_WINDOW_RANKING_RULE,
        "PICK_COUNT": PICK_COUNT,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "RNG_SEED": None,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_WINDOWS": WINDOWS,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "TICKET_COUNT": ticket_count,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
        "WINDOWS": WINDOWS,
        "WINDOW_FUSION_RULE": WINDOW_FUSION_RULE,
        "WINDOW_NORMALIZATION_RULE": WINDOW_NORMALIZATION_RULE,
        "GRAPH_NODE_DOMAIN": GRAPH_NODE_DOMAIN,
    }


def _build_candidate_authority() -> tuple[
    tuple[CandidateMetadata, ...],
    Mapping[str, CandidateMetadata],
    Mapping[str, Mapping[str, object]],
    Mapping[tuple[str, int], str],
]:
    authorities: list[CandidateMetadata] = []
    metadata_by_id: dict[str, CandidateMetadata] = {}
    semantics_by_id: dict[str, Mapping[str, object]] = {}
    ids_by_pair: dict[tuple[str, int], str] = {}

    for constructor_id in CONSTRUCTOR_IDS:
        for ticket_count in TICKET_COUNTS:
            semantic_record = _candidate_semantic_record(constructor_id, ticket_count)
            identity = derive_candidate_identity(semantic_record)
            if identity.CANDIDATE_ID in metadata_by_id:
                raise RuntimeError("candidate ID collision in frozen graph hypothesis matrix")
            semantic_proxy: Mapping[str, object] = MappingProxyType(semantic_record)
            metadata = CandidateMetadata(
                CANDIDATE_ID=identity.CANDIDATE_ID,
                SIGNATURE_HASH=identity.SIGNATURE_HASH,
                SEMANTICS=semantic_proxy,
                CONSTRUCTOR_ID=constructor_id,
                TICKET_COUNT=ticket_count,
                IMPLEMENTATION_SYMBOL=_implementation_symbol(constructor_id, ticket_count),
            )
            authorities.append(metadata)
            metadata_by_id[identity.CANDIDATE_ID] = metadata
            semantics_by_id[identity.CANDIDATE_ID] = semantic_proxy
            ids_by_pair[(constructor_id, ticket_count)] = identity.CANDIDATE_ID

    if len(authorities) != len(CONSTRUCTOR_IDS) * len(TICKET_COUNTS):
        raise RuntimeError("candidate authority matrix is not exactly 3 by 3")
    if len({metadata.SIGNATURE_HASH for metadata in authorities}) != len(authorities):
        raise RuntimeError("candidate signature collision in frozen graph hypothesis matrix")
    return (
        tuple(authorities),
        MappingProxyType(metadata_by_id),
        MappingProxyType(semantics_by_id),
        MappingProxyType(ids_by_pair),
    )


(
    CANDIDATE_AUTHORITIES,
    CANDIDATE_METADATA,
    CANDIDATE_SEMANTICS,
    CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT,
) = _build_candidate_authority()
CANDIDATE_AUTHORITY: Final[Mapping[str, CandidateMetadata]] = CANDIDATE_METADATA
CANDIDATE_IDS: Final[tuple[str, ...]] = tuple(
    metadata.CANDIDATE_ID for metadata in CANDIDATE_AUTHORITIES
)
CANDIDATE_SIGNATURE_HASHES: Final[tuple[str, ...]] = tuple(
    metadata.SIGNATURE_HASH for metadata in CANDIDATE_AUTHORITIES
)


def candidate_id_for(constructor_id: str, ticket_count: int) -> str:
    """Return the frozen candidate ID for one constructor/budget pair."""

    try:
        return CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT[(constructor_id, ticket_count)]
    except KeyError as error:
        raise KeyError(
            f"unsupported constructor/budget pair: {constructor_id!r}, {ticket_count!r}"
        ) from error


def _metadata_for_candidate(candidate_id: str) -> CandidateMetadata:
    try:
        return CANDIDATE_METADATA[candidate_id]
    except KeyError as error:
        raise KeyError(f"unknown candidate_id: {candidate_id!r}") from error


def produce_biglotto_graph_network_multi_ticket_candidate(
    candidate_id: str, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce one frozen graph portfolio from strictly prior history."""

    metadata = _metadata_for_candidate(candidate_id)
    source_tickets = produce_source_ticket_universe(history, target_index)
    constructor = _constructors.CONSTRUCTORS[metadata.CONSTRUCTOR_ID]
    return constructor(source_tickets, metadata.TICKET_COUNT)


produce_biglotto_multi_ticket_candidate = produce_biglotto_graph_network_multi_ticket_candidate
produce_multi_ticket_candidate = produce_biglotto_graph_network_multi_ticket_candidate
produce_candidate_portfolio = produce_biglotto_graph_network_multi_ticket_candidate


def _produce_named_candidate(
    constructor_id: str, ticket_count: int, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return produce_biglotto_graph_network_multi_ticket_candidate(
        candidate_id_for(constructor_id, ticket_count), history, target_index
    )


def produce_b649_graph_network_multiticket_low_overlap_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 5, history, target_index)


def produce_b649_graph_network_multiticket_low_overlap_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 10, history, target_index)


def produce_b649_graph_network_multiticket_low_overlap_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 20, history, target_index)


def produce_b649_graph_network_multiticket_exposure_balanced_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 5, history, target_index)


def produce_b649_graph_network_multiticket_exposure_balanced_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 10, history, target_index)


def produce_b649_graph_network_multiticket_exposure_balanced_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 20, history, target_index)


def produce_b649_graph_network_multiticket_hybrid_diversity_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 5, history, target_index)


def produce_b649_graph_network_multiticket_hybrid_diversity_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 10, history, target_index)


def produce_b649_graph_network_multiticket_hybrid_diversity_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 20, history, target_index)


__all__ = [
    "CANDIDATE_AUTHORITIES",
    "CANDIDATE_AUTHORITY",
    "CANDIDATE_IDS",
    "CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT",
    "CANDIDATE_METADATA",
    "CANDIDATE_SEMANTICS",
    "CANDIDATE_SIGNATURE_HASHES",
    "CAUSAL_CUTOFF_RULE",
    "CONSTRUCTOR_IDS",
    "DETERMINISM_CLASS",
    "EDGE_DEFINITION",
    "EDGE_WEIGHT_RULE",
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "GRAPH_NODE_COUNT",
    "GRAPH_NODE_DOMAIN",
    "HISTORY_ORDER",
    "HYPOTHESIS_VERSION",
    "LOTTERY_TYPE",
    "METHOD_FAMILY",
    "MINIMUM_HISTORY",
    "NUMBER_DOMAIN",
    "OUTPUT_SHAPE",
    "PAGERANK_ARITHMETIC",
    "PAGERANK_DAMPING",
    "PAGERANK_DANGLING_RULE",
    "PAGERANK_INITIALIZATION",
    "PAGERANK_ITERATIONS",
    "PER_WINDOW_RANKING_RULE",
    "PICK_COUNT",
    "RNG_SEMANTICS",
    "ROBUSTNESS_RULE",
    "SOURCE_CANDIDATE_TICKET_COUNT",
    "SOURCE_TICKET_ORDER",
    "SOURCE_UNIVERSE_CONTRACT",
    "SOURCE_UNIVERSE_ID",
    "SOURCE_UNIVERSE_METADATA",
    "SOURCE_UNIVERSE_VERSION",
    "SOURCE_WINDOWS",
    "TICKET_COUNTS",
    "TOP_NUMBER_COUNT",
    "WINDOWS",
    "WINDOW_FUSION_RULE",
    "WINDOW_NORMALIZATION_RULE",
    "FusedNumberRanking",
    "GraphWindow",
    "InsufficientHistoryError",
    "WindowRanking",
    "build_cooccurrence_edge_counts",
    "build_cooccurrence_graph",
    "build_graph_for_window",
    "build_source_ticket_universe",
    "calculate_exact_pagerank",
    "calculate_fused_number_ranking",
    "calculate_graph_for_window",
    "calculate_graph_rankings",
    "calculate_page_rank",
    "calculate_window_rankings",
    "candidate_id_for",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "exact_pagerank",
    "fuse_window_rankings",
    "produce_b649_graph_network_multiticket_exposure_balanced_v1_k5",
    "produce_b649_graph_network_multiticket_exposure_balanced_v1_k10",
    "produce_b649_graph_network_multiticket_exposure_balanced_v1_k20",
    "produce_b649_graph_network_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_graph_network_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_graph_network_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_graph_network_multiticket_low_overlap_v1_k5",
    "produce_b649_graph_network_multiticket_low_overlap_v1_k10",
    "produce_b649_graph_network_multiticket_low_overlap_v1_k20",
    "produce_b649_multiscale_graph_pagerank_ranked_pool_v1",
    "produce_biglotto_graph_network_multi_ticket_candidate",
    "produce_biglotto_multi_ticket_candidate",
    "produce_candidate_portfolio",
    "produce_multi_ticket_candidate",
    "produce_source_ticket_universe",
    "rank_numbers_by_window",
    "raw_frequency_order_for_window",
    "signature_hash_for_semantics",
    "validate_prior_history",
]
