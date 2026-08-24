"""Causal conditional-cooccurrence BigLotto multi-ticket candidate batch R1.

This module freezes one history-only source-ticket universe based on
same-draw co-occurrence conditional on the most recent completed draw.  It
combines that source with the three frozen candidate-set constructors at the
three native portfolio budgets.  It has no outcome access, fitted parameters,
randomness, I/O, or production catalog registration.
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
type TicketPortfolio = tuple[Ticket, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
SOURCE_UNIVERSE_ID: Final[str] = "B649_CONDITIONAL_COOCCURRENCE_RANKED_POOL_V1"
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
SOURCE_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
MINIMUM_HISTORY: Final[int] = 751
TOP_NUMBER_COUNT: Final[int] = 10
SOURCE_CANDIDATE_TICKET_COUNT: Final[int] = 210
SOURCE_TICKET_ORDER: Final[str] = "LEXICOGRAPHIC_RANK_POSITION_COMBINATION_ORDER"

ANCHOR_RULE: Final[str] = "ANCHOR_DRAW=HISTORY[TARGET_INDEX-1]"
OCCURRENCE_FORMULA: Final[str] = "OCCURRENCE_W(a)=COUNT_ESTIMATION_DRAWS_CONTAINING(a)"
PAIR_COUNT_FORMULA: Final[str] = (
    "PAIR_COUNT_W(a,n)=COUNT_ESTIMATION_DRAWS_CONTAINING_BOTH(a,n);a_IN_ANCHOR;n!=a"
)
ZERO_OCCURRENCE_RULE: Final[str] = "OCCURRENCE_W(a)=0_IMPLIES_CONTRIBUTION_W(a,n)=0"
SELF_ANCHOR_RULE: Final[str] = "SELF_ANCHOR_N_EQUALS_A_CONTRIBUTES_ZERO"
COOCCURRENCE_SCORE_RULE: Final[str] = (
    "SCORE_W(n)=SUM_ANCHOR_A_NOT_EQUAL_N(PAIR_COUNT_W(a,n)/OCCURRENCE_W(a))"
)
NUMBER_RANKING_RULE: Final[str] = "COOCCURRENCE_SCORE_DESCENDING_NUMBER_ASCENDING"
WINDOW_NORMALIZATION_RULE: Final[str] = "NORMALIZED=(49-POSITION)/48"
WINDOW_FUSION_RULE: Final[str] = (
    "EQUAL_WEIGHT_MEAN;ROBUSTNESS=(MINIMUM,MEDIAN,MAXIMUM);"
    "FINAL=MEAN_DESC,ROBUSTNESS_MIN_DESC,ROBUSTNESS_MEDIAN_DESC,"
    "ROBUSTNESS_MAX_DESC,NUMBER_ASC"
)
ROBUSTNESS_RULE: Final[str] = "ROBUSTNESS_SORTED_ASCENDING=(MINIMUM,MEDIAN,MAXIMUM)"
CAUSAL_CUTOFF_RULE: Final[str] = (
    "STRICTLY_PRIOR_ESTIMATION_PLUS_LAST_COMPLETED_DRAW_ANCHOR"
)
PARAMETER_SELECTION_RULE: Final[str] = "FIXED_PREREGISTERED_NO_OUTCOME_TUNING"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
SOURCE_EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "LAST_DRAW_CONDITIONAL_COOCCURRENCE_STRUCTURE"
)

CONSTRUCTOR_IDS: Final[tuple[str, str, str]] = (
    "B649_CANDIDATE_SET_LOW_OVERLAP_V1",
    "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1",
    "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1",
)
TICKET_COUNTS: Final[tuple[int, int, int]] = (5, 10, 20)

_CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "TICKET_PAIRWISE_DIVERSITY",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "NUMBER_EXPOSURE_DIVERSITY",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": (
            "PAIRWISE_AND_NUMBER_EXPOSURE_DIVERSITY"
        ),
    }
)
_CONSTRUCTOR_SYMBOL_SLUGS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "low_overlap",
        "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": "exposure_balanced",
        "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": "hybrid_diversity",
    }
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the preregistered 751 prior draws are available."""


@dataclass(frozen=True, slots=True)
class SourceUniverseMetadata:
    """Immutable metadata for the conditional-cooccurrence source universe."""

    SOURCE_UNIVERSE_ID: str
    VERSION: str
    LOTTERY_TYPE: str
    PICK_COUNT: int
    NUMBER_DOMAIN: tuple[int, int]
    HISTORY_ORDER: str
    WINDOWS: tuple[int, int, int]
    MINIMUM_HISTORY: int
    ANCHOR_RULE: str
    OCCURRENCE_FORMULA: str
    PAIR_COUNT_FORMULA: str
    ZERO_OCCURRENCE_RULE: str
    SELF_ANCHOR_RULE: str
    COOCCURRENCE_SCORE_RULE: str
    NUMBER_RANKING_RULE: str
    WINDOW_NORMALIZATION_RULE: str
    WINDOW_FUSION_RULE: str
    ROBUSTNESS_RULE: str
    TOP_NUMBER_COUNT: int
    SOURCE_CANDIDATE_TICKET_COUNT: int
    SOURCE_TICKET_ORDER: str
    CAUSAL_CUTOFF_RULE: str
    PARAMETER_SELECTION_RULE: str
    DETERMINISM_CLASS: str
    RNG_SEMANTICS: str
    EXPECTED_IMPROVEMENT_CHANNEL: str


SOURCE_UNIVERSE_METADATA: Final[SourceUniverseMetadata] = SourceUniverseMetadata(
    SOURCE_UNIVERSE_ID=SOURCE_UNIVERSE_ID,
    VERSION=SOURCE_UNIVERSE_VERSION,
    LOTTERY_TYPE=LOTTERY_TYPE,
    PICK_COUNT=PICK_COUNT,
    NUMBER_DOMAIN=NUMBER_DOMAIN,
    HISTORY_ORDER=HISTORY_ORDER,
    WINDOWS=SOURCE_WINDOWS,
    MINIMUM_HISTORY=MINIMUM_HISTORY,
    ANCHOR_RULE=ANCHOR_RULE,
    OCCURRENCE_FORMULA=OCCURRENCE_FORMULA,
    PAIR_COUNT_FORMULA=PAIR_COUNT_FORMULA,
    ZERO_OCCURRENCE_RULE=ZERO_OCCURRENCE_RULE,
    SELF_ANCHOR_RULE=SELF_ANCHOR_RULE,
    COOCCURRENCE_SCORE_RULE=COOCCURRENCE_SCORE_RULE,
    NUMBER_RANKING_RULE=NUMBER_RANKING_RULE,
    WINDOW_NORMALIZATION_RULE=WINDOW_NORMALIZATION_RULE,
    WINDOW_FUSION_RULE=WINDOW_FUSION_RULE,
    ROBUSTNESS_RULE=ROBUSTNESS_RULE,
    TOP_NUMBER_COUNT=TOP_NUMBER_COUNT,
    SOURCE_CANDIDATE_TICKET_COUNT=SOURCE_CANDIDATE_TICKET_COUNT,
    SOURCE_TICKET_ORDER=SOURCE_TICKET_ORDER,
    CAUSAL_CUTOFF_RULE=CAUSAL_CUTOFF_RULE,
    PARAMETER_SELECTION_RULE=PARAMETER_SELECTION_RULE,
    DETERMINISM_CLASS=DETERMINISM_CLASS,
    RNG_SEMANTICS=RNG_SEMANTICS,
    EXPECTED_IMPROVEMENT_CHANNEL=SOURCE_EXPECTED_IMPROVEMENT_CHANNEL,
)

SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = MappingProxyType(
    {
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "PICK_COUNT": PICK_COUNT,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "HISTORY_ORDER": HISTORY_ORDER,
        "WINDOWS": SOURCE_WINDOWS,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "ANCHOR_RULE": ANCHOR_RULE,
        "OCCURRENCE_FORMULA": OCCURRENCE_FORMULA,
        "PAIR_COUNT_FORMULA": PAIR_COUNT_FORMULA,
        "ZERO_OCCURRENCE_RULE": ZERO_OCCURRENCE_RULE,
        "SELF_ANCHOR_RULE": SELF_ANCHOR_RULE,
        "COOCCURRENCE_SCORE_RULE": COOCCURRENCE_SCORE_RULE,
        "NUMBER_RANKING_RULE": NUMBER_RANKING_RULE,
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
        "SOURCE_EXPECTED_IMPROVEMENT_CHANNEL": SOURCE_EXPECTED_IMPROVEMENT_CHANNEL,
    }
)


@dataclass(frozen=True, slots=True)
class WindowRanking:
    """Exact conditional-cooccurrence details and ranks for one window."""

    WINDOW: int
    ANCHOR_DRAW: HistoryDraw
    ESTIMATION_DRAW_COUNT: int
    OCCURRENCES: tuple[int, ...]
    PAIR_COUNTS: tuple[tuple[int, ...], ...]
    CONTRIBUTIONS: tuple[tuple[Fraction, ...], ...]
    SCORES: tuple[Fraction, ...]
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: tuple[Fraction, ...]

    def occurrence(self, anchor_number: int) -> int:
        _validate_number(anchor_number)
        return self.OCCURRENCES[anchor_number - 1]

    def pair_count(self, anchor_number: int, candidate_number: int) -> int:
        _validate_number(anchor_number)
        _validate_number(candidate_number)
        return self.PAIR_COUNTS[anchor_number - 1][candidate_number - 1]

    def contribution(self, anchor_number: int, candidate_number: int) -> Fraction:
        _validate_number(anchor_number)
        _validate_number(candidate_number)
        return self.CONTRIBUTIONS[anchor_number - 1][candidate_number - 1]

    def score(self, number: int) -> Fraction:
        _validate_number(number)
        return self.SCORES[number - 1]

    def cooccurrence_score(self, number: int) -> Fraction:
        return self.score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]

    @property
    def COOCCURRENCE_SCORES(self) -> tuple[Fraction, ...]:
        return self.SCORES

    @property
    def OCCURRENCE_COUNTS(self) -> tuple[int, ...]:
        return self.OCCURRENCES


@dataclass(frozen=True, slots=True)
class FusedNumberRanking:
    """Three-window fusion with exact rational ranks and robustness values."""

    ORDERED_NUMBERS: tuple[int, ...]
    MEAN_RANKS: tuple[Fraction, ...]
    ROBUSTNESS: tuple[tuple[Fraction, Fraction, Fraction], ...]
    WINDOW_RANKINGS: tuple[WindowRanking, ...]

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
    """Return a validated immutable copy of only the strictly prior history."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    return tuple(_validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix))


def _validate_window(window: int) -> None:
    if type(window) is not int or window not in SOURCE_WINDOWS:
        raise ValueError(f"window must be one of {SOURCE_WINDOWS}")


def _rank_validated_window(
    prior_history: tuple[HistoryDraw, ...], window: int
) -> WindowRanking:
    _validate_window(window)
    if len(prior_history) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"window {window} requires at least {MINIMUM_HISTORY} prior draws"
        )

    anchor_draw = prior_history[-1]
    estimation_draws = prior_history[-1 - window : -1]
    if len(estimation_draws) != window:
        raise InsufficientHistoryError(
            f"window {window} requires {window} draws strictly before the anchor"
        )

    occurrences = [0] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    pair_counts = [
        [0] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
        for _ in range(NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    ]
    anchor_numbers = frozenset(anchor_draw)

    for raw_draw in estimation_draws:
        draw_numbers = frozenset(raw_draw)
        for anchor_number in anchor_numbers:
            if anchor_number not in draw_numbers:
                continue
            occurrences[anchor_number - 1] += 1
            for candidate_number in draw_numbers:
                if candidate_number != anchor_number:
                    pair_counts[anchor_number - 1][candidate_number - 1] += 1

    contributions = [
        [Fraction(0, 1)] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
        for _ in range(NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    ]
    scores = [Fraction(0, 1)] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    for anchor_number in anchor_numbers:
        denominator = occurrences[anchor_number - 1]
        for candidate_number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1):
            if candidate_number == anchor_number or denominator == 0:
                continue
            contribution = Fraction(
                pair_counts[anchor_number - 1][candidate_number - 1], denominator
            )
            contributions[anchor_number - 1][candidate_number - 1] = contribution
            scores[candidate_number - 1] += contribution

    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-scores[number - 1], number),
        )
    )
    positions = [0] * len(scores)
    normalized_ranks: list[Fraction] = [Fraction(0, 1)] * len(scores)
    for position, number in enumerate(ordered_numbers, start=1):
        positions[number - 1] = position
        normalized_ranks[number - 1] = Fraction(49 - position, 48)

    return WindowRanking(
        WINDOW=window,
        ANCHOR_DRAW=anchor_draw,
        ESTIMATION_DRAW_COUNT=len(estimation_draws),
        OCCURRENCES=tuple(occurrences),
        PAIR_COUNTS=tuple(tuple(row) for row in pair_counts),
        CONTRIBUTIONS=tuple(tuple(row) for row in contributions),
        SCORES=tuple(scores),
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized_ranks),
    )


def rank_numbers_by_window(
    history: HistoryInput, target_index: int, window: int
) -> WindowRanking:
    """Rank all 49 numbers using exact conditional co-occurrence for one window."""

    return _rank_validated_window(validate_prior_history(history, target_index), window)


calculate_conditional_cooccurrence_window = rank_numbers_by_window


def calculate_conditional_cooccurrence_scores(
    history: HistoryInput, target_index: int, window: int
) -> tuple[Fraction, ...]:
    """Return the exact per-number score vector for one estimation window."""

    return rank_numbers_by_window(history, target_index, window).SCORES


def calculate_window_rankings(
    history: HistoryInput, target_index: int
) -> tuple[WindowRanking, WindowRanking, WindowRanking]:
    """Calculate the exact 50/300/750 conditional-cooccurrence rankings."""

    prior_history = validate_prior_history(history, target_index)
    rankings = tuple(_rank_validated_window(prior_history, window) for window in SOURCE_WINDOWS)
    return cast(tuple[WindowRanking, WindowRanking, WindowRanking], rankings)


def fuse_window_rankings(
    window_rankings: Sequence[WindowRanking],
) -> FusedNumberRanking:
    """Fuse the three window rankings with equal exact rational weight."""

    if tuple(ranking.WINDOW for ranking in window_rankings) != SOURCE_WINDOWS:
        raise ValueError(f"window_rankings must contain windows in order {SOURCE_WINDOWS}")

    mean_ranks: list[Fraction] = []
    robustness: list[tuple[Fraction, Fraction, Fraction]] = []
    for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1):
        ranks = tuple(ranking.normalized_rank(number) for ranking in window_rankings)
        mean_ranks.append(sum(ranks, Fraction(0, 1)) / 3)
        sorted_ranks = tuple(sorted(ranks))
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
    """Calculate the final three-window fused number ranking."""

    return fuse_window_rankings(calculate_window_rankings(history, target_index))


def produce_b649_conditional_cooccurrence_ranked_pool_v1(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce the ordered 210-ticket source universe from prior history only."""

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


produce_source_ticket_universe = produce_b649_conditional_cooccurrence_ranked_pool_v1
build_source_ticket_universe = produce_b649_conditional_cooccurrence_ranked_pool_v1


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
        items = cast(tuple[object, ...], value)
        return [_json_ready(item) for item in items]
    if isinstance(value, list):
        items = cast(list[object], value)
        return [_json_ready(item) for item in items]
    return value


def canonicalize_semantic_record(record: object) -> bytes:
    """Return sorted-key, compact UTF-8 JSON for one complete semantic record."""

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
    """Derive the frozen candidate ID from a complete semantic record."""

    return f"BMSGV1_MT_{signature_hash_for_semantics(record)[:16]}"


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """Deterministic identity material for one semantic record."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    """Derive candidate ID and full signature hash together."""

    canonical_json = canonical_semantic_json(record)
    signature_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return CandidateIdentity(
        CANDIDATE_ID=f"BMSGV1_MT_{signature_hash[:16]}",
        SIGNATURE_HASH=signature_hash,
        CANONICAL_SEMANTIC_JSON=canonical_json,
    )


@dataclass(frozen=True, slots=True)
class CandidateMetadata:
    """Immutable authority metadata for one frozen research hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    SEMANTICS: Mapping[str, object]
    CONSTRUCTOR_ID: str
    TICKET_COUNT: int
    IMPLEMENTATION_SYMBOL: str


def _implementation_symbol(constructor_id: str, ticket_count: int) -> str:
    return (
        "produce_b649_conditional_cooccurrence_multiticket_"
        f"{_CONSTRUCTOR_SYMBOL_SLUGS[constructor_id]}_v1_k{ticket_count}"
    )


def _candidate_semantic_record(
    constructor_id: str, ticket_count: int
) -> dict[str, object]:
    constructor_metadata = _constructors.CONSTRUCTOR_METADATA[constructor_id]
    return {
        "ANCHOR_RULE": ANCHOR_RULE,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "COOCCURRENCE_SCORE_RULE": COOCCURRENCE_SCORE_RULE,
        "CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNEL": (
            _CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS[constructor_id]
        ),
        "CONSTRUCTOR_ID": constructor_id,
        "CONSTRUCTOR_VERSION": constructor_metadata.VERSION,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "NATIVE_TICKET_COUNT": ticket_count,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "NUMBER_RANKING_RULE": NUMBER_RANKING_RULE,
        "OCCURRENCE_FORMULA": OCCURRENCE_FORMULA,
        "OUTPUT_SHAPE": OUTPUT_SHAPE,
        "PAIR_COUNT_FORMULA": PAIR_COUNT_FORMULA,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "RNG_SEED": None,
        "SELF_ANCHOR_RULE": SELF_ANCHOR_RULE,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_EXPECTED_IMPROVEMENT_CHANNEL": SOURCE_EXPECTED_IMPROVEMENT_CHANNEL,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "TICKET_COUNT": ticket_count,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
        "WINDOWS": SOURCE_WINDOWS,
        "WINDOW_FUSION_RULE": WINDOW_FUSION_RULE,
        "WINDOW_NORMALIZATION_RULE": WINDOW_NORMALIZATION_RULE,
        "ZERO_OCCURRENCE_RULE": ZERO_OCCURRENCE_RULE,
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
                raise RuntimeError("candidate ID collision in frozen hypothesis matrix")
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

    expected_count = len(CONSTRUCTOR_IDS) * len(TICKET_COUNTS)
    if len(authorities) != expected_count:
        raise RuntimeError("candidate authority matrix is not exactly 3 by 3")
    if len({metadata.SIGNATURE_HASH for metadata in authorities}) != len(authorities):
        raise RuntimeError("candidate signature collision in frozen hypothesis matrix")
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


def produce_biglotto_conditional_cooccurrence_multi_ticket_candidate(
    candidate_id: str, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce one frozen candidate portfolio from strictly prior history."""

    metadata = _metadata_for_candidate(candidate_id)
    source_tickets = produce_source_ticket_universe(history, target_index)
    constructor = _constructors.CONSTRUCTORS[metadata.CONSTRUCTOR_ID]
    return constructor(source_tickets, metadata.TICKET_COUNT)


produce_biglotto_multi_ticket_candidate = (
    produce_biglotto_conditional_cooccurrence_multi_ticket_candidate
)
produce_multi_ticket_candidate = produce_biglotto_conditional_cooccurrence_multi_ticket_candidate
produce_candidate_portfolio = produce_biglotto_conditional_cooccurrence_multi_ticket_candidate


def produce_b649_conditional_cooccurrence_multiticket_low_overlap_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return produce_biglotto_conditional_cooccurrence_multi_ticket_candidate(
        candidate_id_for("B649_CANDIDATE_SET_LOW_OVERLAP_V1", 5), history, target_index
    )


def produce_b649_conditional_cooccurrence_multiticket_low_overlap_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return produce_biglotto_conditional_cooccurrence_multi_ticket_candidate(
        candidate_id_for("B649_CANDIDATE_SET_LOW_OVERLAP_V1", 10), history, target_index
    )


def produce_b649_conditional_cooccurrence_multiticket_low_overlap_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return produce_biglotto_conditional_cooccurrence_multi_ticket_candidate(
        candidate_id_for("B649_CANDIDATE_SET_LOW_OVERLAP_V1", 20), history, target_index
    )


def produce_b649_conditional_cooccurrence_multiticket_exposure_balanced_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return produce_biglotto_conditional_cooccurrence_multi_ticket_candidate(
        candidate_id_for("B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1", 5), history, target_index
    )


def produce_b649_conditional_cooccurrence_multiticket_exposure_balanced_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return produce_biglotto_conditional_cooccurrence_multi_ticket_candidate(
        candidate_id_for("B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1", 10), history, target_index
    )


def produce_b649_conditional_cooccurrence_multiticket_exposure_balanced_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return produce_biglotto_conditional_cooccurrence_multi_ticket_candidate(
        candidate_id_for("B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1", 20), history, target_index
    )


def produce_b649_conditional_cooccurrence_multiticket_hybrid_diversity_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return produce_biglotto_conditional_cooccurrence_multi_ticket_candidate(
        candidate_id_for("B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1", 5), history, target_index
    )


def produce_b649_conditional_cooccurrence_multiticket_hybrid_diversity_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return produce_biglotto_conditional_cooccurrence_multi_ticket_candidate(
        candidate_id_for("B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1", 10), history, target_index
    )


def produce_b649_conditional_cooccurrence_multiticket_hybrid_diversity_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return produce_biglotto_conditional_cooccurrence_multi_ticket_candidate(
        candidate_id_for("B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1", 20), history, target_index
    )


# Short aliases retain the predecessor's convenient named-producer shape while
# keeping the conditional source family explicit in the canonical symbols.
produce_b649_multiticket_low_overlap_v1_k5 = (
    produce_b649_conditional_cooccurrence_multiticket_low_overlap_v1_k5
)
produce_b649_multiticket_low_overlap_v1_k10 = (
    produce_b649_conditional_cooccurrence_multiticket_low_overlap_v1_k10
)
produce_b649_multiticket_low_overlap_v1_k20 = (
    produce_b649_conditional_cooccurrence_multiticket_low_overlap_v1_k20
)
produce_b649_multiticket_exposure_balanced_v1_k5 = (
    produce_b649_conditional_cooccurrence_multiticket_exposure_balanced_v1_k5
)
produce_b649_multiticket_exposure_balanced_v1_k10 = (
    produce_b649_conditional_cooccurrence_multiticket_exposure_balanced_v1_k10
)
produce_b649_multiticket_exposure_balanced_v1_k20 = (
    produce_b649_conditional_cooccurrence_multiticket_exposure_balanced_v1_k20
)
produce_b649_multiticket_hybrid_diversity_v1_k5 = (
    produce_b649_conditional_cooccurrence_multiticket_hybrid_diversity_v1_k5
)
produce_b649_multiticket_hybrid_diversity_v1_k10 = (
    produce_b649_conditional_cooccurrence_multiticket_hybrid_diversity_v1_k10
)
produce_b649_multiticket_hybrid_diversity_v1_k20 = (
    produce_b649_conditional_cooccurrence_multiticket_hybrid_diversity_v1_k20
)


__all__ = [
    "ANCHOR_RULE",
    "CANDIDATE_AUTHORITIES",
    "CANDIDATE_AUTHORITY",
    "CANDIDATE_IDS",
    "CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT",
    "CANDIDATE_METADATA",
    "CANDIDATE_SEMANTICS",
    "CANDIDATE_SIGNATURE_HASHES",
    "CAUSAL_CUTOFF_RULE",
    "CONSTRUCTOR_IDS",
    "COOCCURRENCE_SCORE_RULE",
    "DETERMINISM_CLASS",
    "HISTORY_ORDER",
    "HYPOTHESIS_VERSION",
    "LOTTERY_TYPE",
    "MINIMUM_HISTORY",
    "NUMBER_DOMAIN",
    "NUMBER_RANKING_RULE",
    "OCCURRENCE_FORMULA",
    "OUTPUT_SHAPE",
    "PAIR_COUNT_FORMULA",
    "PARAMETER_SELECTION_RULE",
    "PICK_COUNT",
    "RNG_SEMANTICS",
    "ROBUSTNESS_RULE",
    "SELF_ANCHOR_RULE",
    "SOURCE_CANDIDATE_TICKET_COUNT",
    "SOURCE_EXPECTED_IMPROVEMENT_CHANNEL",
    "SOURCE_TICKET_ORDER",
    "SOURCE_UNIVERSE_CONTRACT",
    "SOURCE_UNIVERSE_ID",
    "SOURCE_UNIVERSE_METADATA",
    "SOURCE_UNIVERSE_VERSION",
    "SOURCE_WINDOWS",
    "TICKET_COUNTS",
    "TOP_NUMBER_COUNT",
    "WINDOW_FUSION_RULE",
    "WINDOW_NORMALIZATION_RULE",
    "ZERO_OCCURRENCE_RULE",
    "FusedNumberRanking",
    "InsufficientHistoryError",
    "WindowRanking",
    "build_source_ticket_universe",
    "calculate_conditional_cooccurrence_scores",
    "calculate_conditional_cooccurrence_window",
    "calculate_fused_number_ranking",
    "calculate_window_rankings",
    "candidate_id_for",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "fuse_window_rankings",
    "produce_b649_conditional_cooccurrence_multiticket_exposure_balanced_v1_k5",
    "produce_b649_conditional_cooccurrence_multiticket_exposure_balanced_v1_k10",
    "produce_b649_conditional_cooccurrence_multiticket_exposure_balanced_v1_k20",
    "produce_b649_conditional_cooccurrence_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_conditional_cooccurrence_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_conditional_cooccurrence_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_conditional_cooccurrence_multiticket_low_overlap_v1_k5",
    "produce_b649_conditional_cooccurrence_multiticket_low_overlap_v1_k10",
    "produce_b649_conditional_cooccurrence_multiticket_low_overlap_v1_k20",
    "produce_b649_conditional_cooccurrence_ranked_pool_v1",
    "produce_b649_multiticket_exposure_balanced_v1_k5",
    "produce_b649_multiticket_exposure_balanced_v1_k10",
    "produce_b649_multiticket_exposure_balanced_v1_k20",
    "produce_b649_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_multiticket_low_overlap_v1_k5",
    "produce_b649_multiticket_low_overlap_v1_k10",
    "produce_b649_multiticket_low_overlap_v1_k20",
    "produce_biglotto_conditional_cooccurrence_multi_ticket_candidate",
    "produce_biglotto_multi_ticket_candidate",
    "produce_candidate_portfolio",
    "produce_multi_ticket_candidate",
    "produce_source_ticket_universe",
    "rank_numbers_by_window",
    "signature_hash_for_semantics",
    "validate_prior_history",
]
