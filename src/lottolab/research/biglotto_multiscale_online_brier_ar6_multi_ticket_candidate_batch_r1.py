"""Causal BigLotto online Brier AR6 candidate batch R1.

This module freezes one history-only source-ticket universe:
``B649_MULTISCALE_ONLINE_BRIER_AR6_RANKED_POOL_V1``.

Each legal number has an independent fixed six-lag online linear-probability
model at the three preregistered horizons.  The models use exact rational
arithmetic, one chronological pass, and the official marginal inclusion rate
only as their fixed initialization.  The fused top-ten pool produces 210
ordered source tickets, which are passed directly to the three frozen
candidate-set constructors.

The producer has no outcome access, fitted parameter selection, randomness,
I/O, or production catalog registration.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import combinations, islice
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import biglotto_multi_ticket_constructors_r1 as _constructors

type Ticket = tuple[int, int, int, int, int, int]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type BinarySeries = tuple[int, ...]
type FeatureVector = tuple[int, int, int, int, int, int, int]
type Weights = tuple[Fraction, Fraction, Fraction, Fraction, Fraction, Fraction, Fraction]
type RationalRanks = tuple[Fraction, ...]
type RobustnessTuple = tuple[Fraction, Fraction, Fraction]
type TicketPortfolio = tuple[Ticket, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
SOURCE_UNIVERSE_ID: Final[str] = "B649_MULTISCALE_ONLINE_BRIER_AR6_RANKED_POOL_V1"
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"
METHOD_FAMILY: Final[str] = "ML_LIKE"
MODEL_CLASS: Final[str] = "ONLINE_LINEAR_PROBABILITY_AUTOREGRESSION"
LOSS_FAMILY: Final[str] = "BRIER_SQUARED_ERROR"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
PICK_COUNT: Final[int] = 6
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
TRAINING_HORIZONS: Final[tuple[int, int, int]] = (50, 300, 750)
HORIZONS: Final[tuple[int, int, int]] = TRAINING_HORIZONS
WINDOWS: Final[tuple[int, int, int]] = TRAINING_HORIZONS
SOURCE_WINDOWS: Final[tuple[int, int, int]] = TRAINING_HORIZONS
AUTOREGRESSIVE_LAG_DEPTH: Final[int] = 6
AR_LAG_DEPTH: Final[int] = AUTOREGRESSIVE_LAG_DEPTH
LAG_DEPTH: Final[int] = AUTOREGRESSIVE_LAG_DEPTH
FEATURE_DIMENSION: Final[int] = AUTOREGRESSIVE_LAG_DEPTH + 1
MINIMUM_HISTORY: Final[int] = max(TRAINING_HORIZONS) + AUTOREGRESSIVE_LAG_DEPTH
TOP_NUMBER_COUNT: Final[int] = 10
SOURCE_NUMBER_POOL_COUNT: Final[int] = TOP_NUMBER_COUNT
SOURCE_CANDIDATE_TICKET_COUNT: Final[int] = 210
SOURCE_TICKET_ORDER: Final[str] = "LEXICOGRAPHIC_RANK_POSITION_COMBINATION_ORDER"

OFFICIAL_NULL_P0: Final[Fraction] = Fraction(6, 49)
P0: Final[Fraction] = OFFICIAL_NULL_P0
INITIAL_INTERCEPT: Final[Fraction] = OFFICIAL_NULL_P0
INITIAL_LAG_WEIGHTS: Final[tuple[Fraction, ...]] = (Fraction(0, 1),) * LAG_DEPTH
LEARNING_RATE: Final[Fraction] = Fraction(1, 64)
PREDICTION_CLIP: Final[tuple[Fraction, Fraction]] = (Fraction(0, 1), Fraction(1, 1))
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None

FEATURE_RULE: Final[str] = (
    "X_n(t)=(1,Y_n(t-1),Y_n(t-2),Y_n(t-3),Y_n(t-4),Y_n(t-5),Y_n(t-6));"
    "OWN_NUMBER_ONLY;BINARY_EXACT"
)
INITIALIZATION_RULE: Final[str] = (
    "THETA=(6/49,0,0,0,0,0,0);INDEPENDENT_PER_NUMBER_PER_HORIZON;EXACT_RATIONAL"
)
RAW_SCORE_RULE: Final[str] = "RAW_SCORE=THETA_DOT_X;EXACT_RATIONAL"
PREDICTION_RULE: Final[str] = "PREDICTION=CLIP_01(RAW_SCORE);EXACT_RATIONAL"
ONLINE_UPDATE_RULE: Final[str] = (
    "THETA_J<-THETA_J+(1/64)*(Y-PREDICTION)*X_J;ALL_COORDINATES_SAME_PRE_UPDATE_ERROR"
)
TRAINING_RULE: Final[str] = (
    "ONE_PASS;CHRONOLOGICAL_OLDEST_TO_NEWEST;NO_SHUFFLE;EXAMPLES=T-H,...,T-1"
)
TARGET_RULE: Final[str] = "TARGET_FEATURES=Y(T-1),...,Y(T-6);TARGET_LABEL_EXCLUDED"
PREDICTION_CLIP_RULE: Final[str] = "CLIP_01=[0,1]"
ARITHMETIC: Final[str] = "EXACT_RATIONAL_FRACTION"
PER_HORIZON_RANKING_RULE: Final[str] = (
    "TARGET_PROBABILITY_DESCENDING_NUMBER_ASCENDING"
)
WINDOW_NORMALIZATION_RULE: Final[str] = "NORMALIZED=(49-POSITION)/48;EXACT_RATIONAL"
WINDOW_FUSION_RULE: Final[str] = (
    "EQUAL_RANK_AGGREGATION;MEAN=(NORMALIZED_50+NORMALIZED_300+NORMALIZED_750)/3;"
    "ROBUSTNESS_TIE_BREAK"
)
ROBUSTNESS_RULE: Final[str] = "SORTED_ASCENDING=(MINIMUM,MEDIAN,MAXIMUM)"
CAUSAL_CUTOFF_RULE: Final[str] = "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
PARAMETER_SELECTION_RULE: Final[str] = "FIXED_PREREGISTERED_NO_OUTCOME_TUNING"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
TARGET_OUTCOME_USED: Final[str] = "NO"
FEATURE_SELECTION: Final[str] = "FIXED_OWN_NUMBER_LAGS_1_TO_6"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "CAUSAL_ONLINE_LEARNING_OF_NUMBER_SPECIFIC_SHORT_MEMORY_AUTOREGRESSIVE_STRUCTURE"
)

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
    """Raised when fewer than the preregistered 756 prior draws are available."""


@dataclass(frozen=True, slots=True)
class SourceUniverseMetadata:
    """Immutable authority metadata for the online AR6 source universe."""

    SOURCE_UNIVERSE_ID: str
    VERSION: str
    METHOD_FAMILY: str
    MODEL_CLASS: str
    LOSS_FAMILY: str
    LOTTERY_TYPE: str
    PICK_COUNT: int
    NUMBER_DOMAIN: tuple[int, int]
    HISTORY_ORDER: str
    TRAINING_HORIZONS: tuple[int, int, int]
    AUTOREGRESSIVE_LAG_DEPTH: int
    FEATURE_DIMENSION: int
    MINIMUM_HISTORY: int
    OFFICIAL_NULL_P0: Fraction
    INITIAL_INTERCEPT: Fraction
    INITIAL_LAG_WEIGHTS: tuple[Fraction, ...]
    LEARNING_RATE: Fraction
    ARITHMETIC: str
    FEATURE_RULE: str
    INITIALIZATION_RULE: str
    RAW_SCORE_RULE: str
    PREDICTION_RULE: str
    ONLINE_UPDATE_RULE: str
    TRAINING_RULE: str
    TARGET_RULE: str
    PREDICTION_CLIP_RULE: str
    PER_HORIZON_RANKING_RULE: str
    WINDOW_NORMALIZATION_RULE: str
    WINDOW_FUSION_RULE: str
    ROBUSTNESS_RULE: str
    TOP_NUMBER_COUNT: int
    SOURCE_NUMBER_POOL_COUNT: int
    SOURCE_CANDIDATE_TICKET_COUNT: int
    SOURCE_TICKET_ORDER: str
    CAUSAL_CUTOFF_RULE: str
    PARAMETER_SELECTION_RULE: str
    DETERMINISM_CLASS: str
    RNG_SEMANTICS: str
    TARGET_OUTCOME_USED: str
    EXPECTED_IMPROVEMENT_CHANNEL: str


SOURCE_UNIVERSE_METADATA: Final[SourceUniverseMetadata] = SourceUniverseMetadata(
    SOURCE_UNIVERSE_ID=SOURCE_UNIVERSE_ID,
    VERSION=SOURCE_UNIVERSE_VERSION,
    METHOD_FAMILY=METHOD_FAMILY,
    MODEL_CLASS=MODEL_CLASS,
    LOSS_FAMILY=LOSS_FAMILY,
    LOTTERY_TYPE=LOTTERY_TYPE,
    PICK_COUNT=PICK_COUNT,
    NUMBER_DOMAIN=NUMBER_DOMAIN,
    HISTORY_ORDER=HISTORY_ORDER,
    TRAINING_HORIZONS=TRAINING_HORIZONS,
    AUTOREGRESSIVE_LAG_DEPTH=AUTOREGRESSIVE_LAG_DEPTH,
    FEATURE_DIMENSION=FEATURE_DIMENSION,
    MINIMUM_HISTORY=MINIMUM_HISTORY,
    OFFICIAL_NULL_P0=OFFICIAL_NULL_P0,
    INITIAL_INTERCEPT=INITIAL_INTERCEPT,
    INITIAL_LAG_WEIGHTS=INITIAL_LAG_WEIGHTS,
    LEARNING_RATE=LEARNING_RATE,
    ARITHMETIC=ARITHMETIC,
    FEATURE_RULE=FEATURE_RULE,
    INITIALIZATION_RULE=INITIALIZATION_RULE,
    RAW_SCORE_RULE=RAW_SCORE_RULE,
    PREDICTION_RULE=PREDICTION_RULE,
    ONLINE_UPDATE_RULE=ONLINE_UPDATE_RULE,
    TRAINING_RULE=TRAINING_RULE,
    TARGET_RULE=TARGET_RULE,
    PREDICTION_CLIP_RULE=PREDICTION_CLIP_RULE,
    PER_HORIZON_RANKING_RULE=PER_HORIZON_RANKING_RULE,
    WINDOW_NORMALIZATION_RULE=WINDOW_NORMALIZATION_RULE,
    WINDOW_FUSION_RULE=WINDOW_FUSION_RULE,
    ROBUSTNESS_RULE=ROBUSTNESS_RULE,
    TOP_NUMBER_COUNT=TOP_NUMBER_COUNT,
    SOURCE_NUMBER_POOL_COUNT=SOURCE_NUMBER_POOL_COUNT,
    SOURCE_CANDIDATE_TICKET_COUNT=SOURCE_CANDIDATE_TICKET_COUNT,
    SOURCE_TICKET_ORDER=SOURCE_TICKET_ORDER,
    CAUSAL_CUTOFF_RULE=CAUSAL_CUTOFF_RULE,
    PARAMETER_SELECTION_RULE=PARAMETER_SELECTION_RULE,
    DETERMINISM_CLASS=DETERMINISM_CLASS,
    RNG_SEMANTICS=RNG_SEMANTICS,
    TARGET_OUTCOME_USED=TARGET_OUTCOME_USED,
    EXPECTED_IMPROVEMENT_CHANNEL=EXPECTED_IMPROVEMENT_CHANNEL,
)

SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = MappingProxyType(
    {
        "ARITHMETIC": ARITHMETIC,
        "AUTOREGRESSIVE_LAG_DEPTH": AUTOREGRESSIVE_LAG_DEPTH,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FEATURE_DIMENSION": FEATURE_DIMENSION,
        "FEATURE_RULE": FEATURE_RULE,
        "FEATURE_SELECTION": FEATURE_SELECTION,
        "HISTORY_ORDER": HISTORY_ORDER,
        "HORIZONS": TRAINING_HORIZONS,
        "WINDOWS": WINDOWS,
        "OFFICIAL_NULL_P0": OFFICIAL_NULL_P0,
        "INITIAL_INTERCEPT": INITIAL_INTERCEPT,
        "INITIAL_LAG_WEIGHTS": INITIAL_LAG_WEIGHTS,
        "INITIALIZATION_RULE": INITIALIZATION_RULE,
        "LEARNING_RATE": LEARNING_RATE,
        "LOSS_FAMILY": LOSS_FAMILY,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "MODEL_CLASS": MODEL_CLASS,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "ONLINE_UPDATE_RULE": ONLINE_UPDATE_RULE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PER_HORIZON_RANKING_RULE": PER_HORIZON_RANKING_RULE,
        "PICK_COUNT": PICK_COUNT,
        "PREDICTION_CLIP": PREDICTION_CLIP,
        "PREDICTION_CLIP_RULE": PREDICTION_CLIP_RULE,
        "PREDICTION_RULE": PREDICTION_RULE,
        "RAW_SCORE_RULE": RAW_SCORE_RULE,
        "RNG": RNG,
        "RNG_SEED": None,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_NUMBER_POOL_COUNT": SOURCE_NUMBER_POOL_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "TARGET_OUTCOME_USED": TARGET_OUTCOME_USED,
        "TARGET_RULE": TARGET_RULE,
        "TICKET_COUNTS": TICKET_COUNTS,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
        "TRAINING_HORIZONS": TRAINING_HORIZONS,
        "TRAINING_RULE": TRAINING_RULE,
        "WINDOW_FUSION_RULE": WINDOW_FUSION_RULE,
        "WINDOW_NORMALIZATION_RULE": WINDOW_NORMALIZATION_RULE,
    }
)


@dataclass(frozen=True, slots=True)
class HorizonModel:
    """One exact online model for one number and one fixed horizon."""

    NUMBER: int
    HORIZON: int
    TRAINING_START: int
    TRAINING_END_EXCLUSIVE: int
    INITIAL_WEIGHTS: Weights
    WEIGHTS: Weights
    TARGET_FEATURE: FeatureVector
    TARGET_RAW_SCORE: Fraction
    TARGET_PROBABILITY: Fraction
    TRAINING_EXAMPLES: tuple[int, ...]
    TRAINING_FEATURES: tuple[FeatureVector, ...]
    TRAINING_LABELS: tuple[int, ...]
    TRAINING_PREDICTIONS: RationalRanks
    TRAINING_ERRORS: RationalRanks
    BRIER_LOSSES: RationalRanks

    @property
    def THETA(self) -> Weights:
        return self.WEIGHTS

    @property
    def FINAL_WEIGHTS(self) -> Weights:
        return self.WEIGHTS

    @property
    def RAW_SCORE(self) -> Fraction:
        return self.TARGET_RAW_SCORE

    @property
    def PREDICTION(self) -> Fraction:
        return self.TARGET_PROBABILITY

    @property
    def TARGET_SCORE(self) -> Fraction:
        return self.TARGET_PROBABILITY

    @property
    def TARGET_RAW(self) -> Fraction:
        return self.TARGET_RAW_SCORE

    @property
    def LEARNING_RATE(self) -> Fraction:
        return globals()["LEARNING_RATE"]


OnlineLinearProbabilityModel = HorizonModel
OnlineModel = HorizonModel


@dataclass(frozen=True, slots=True)
class HorizonRanking:
    """Exact target probabilities, ranks, and models for one horizon."""

    HORIZON: int
    TARGET_PROBABILITIES: RationalRanks
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: RationalRanks
    MODELS: tuple[HorizonModel, ...] = ()

    @property
    def WINDOW(self) -> int:
        return self.HORIZON

    @property
    def SCORES(self) -> RationalRanks:
        return self.TARGET_PROBABILITIES

    @property
    def PROBABILITIES(self) -> RationalRanks:
        return self.TARGET_PROBABILITIES

    @property
    def TARGET_SCORES(self) -> RationalRanks:
        return self.TARGET_PROBABILITIES

    @property
    def RANKED_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS

    def target_probability(self, number: int) -> Fraction:
        _validate_number(number)
        return self.TARGET_PROBABILITIES[number - 1]

    def score(self, number: int) -> Fraction:
        return self.target_probability(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]

    def model(self, number: int) -> HorizonModel:
        _validate_number(number)
        if len(self.MODELS) != 49:
            raise ValueError("model details are unavailable for this ranking")
        return self.MODELS[number - 1]


@dataclass(frozen=True, slots=True)
class FusedNumberRanking:
    """Exact equal rank aggregation over the three fixed horizons."""

    ORDERED_NUMBERS: tuple[int, ...]
    MEAN_ML_RANK: RationalRanks
    ROBUSTNESS: tuple[RobustnessTuple, ...]
    HORIZON_RANKINGS: tuple[HorizonRanking, HorizonRanking, HorizonRanking]

    @property
    def TOP_NUMBERS(self) -> tuple[int, ...]:
        return self.ORDERED_NUMBERS[:TOP_NUMBER_COUNT]

    @property
    def MEAN_RANKS(self) -> RationalRanks:
        return self.MEAN_ML_RANK

    @property
    def MEAN_ML_RANKS(self) -> RationalRanks:
        return self.MEAN_ML_RANK

    @property
    def ROBUSTNESS_TUPLES(self) -> tuple[RobustnessTuple, ...]:
        return self.ROBUSTNESS

    @property
    def WINDOW_RANKINGS(self) -> tuple[HorizonRanking, HorizonRanking, HorizonRanking]:
        return self.HORIZON_RANKINGS

    def mean_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.MEAN_ML_RANK[number - 1]

    def mean_ml_rank(self, number: int) -> Fraction:
        return self.mean_rank(number)

    def robustness(self, number: int) -> RobustnessTuple:
        _validate_number(number)
        return self.ROBUSTNESS[number - 1]

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.ORDERED_NUMBERS.index(number) + 1


FusedRanking = FusedNumberRanking


def _validate_number(number: int) -> None:
    if type(number) is not int or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]:
        raise ValueError(f"number must be an integer in {NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}")


def _validate_target_index(target_index: int) -> None:
    if type(target_index) is not int or target_index < 0:
        raise ValueError("target_index must be a non-negative integer")


def _validate_horizon(horizon: int) -> None:
    if type(horizon) is not int or horizon not in TRAINING_HORIZONS:
        raise ValueError(f"horizon must be one of {TRAINING_HORIZONS}")


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
    return cast(HistoryDraw, tuple(sorted(numbers)))


def validate_prior_history(history: HistoryInput, target_index: int) -> tuple[HistoryDraw, ...]:
    """Return an immutable validated copy of strictly prior draws only."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"required minimum {MINIMUM_HISTORY}"
        )
    return tuple(_validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix))


def validate_history(history: HistoryInput, target_index: int) -> tuple[HistoryDraw, ...]:
    """Alias for the strict prior-history validator."""

    return validate_prior_history(history, target_index)


def binary_occurrence(draw: Iterable[object], number: int) -> int:
    """Return the exact binary label for one number in one legal draw."""

    _validate_number(number)
    return int(number in tuple(draw))


def occurrence_label(draw: Iterable[object], number: int) -> int:
    return binary_occurrence(draw, number)


def calculate_binary_occurrence_series(
    history: HistoryInput, number: int
) -> BinarySeries:
    """Return ``Y_n(t)`` for every draw in chronological order."""

    _validate_number(number)
    return tuple(
        binary_occurrence(_validate_draw(raw_draw, index), number)
        for index, raw_draw in enumerate(history)
    )


binary_occurrence_series = calculate_binary_occurrence_series
calculate_occurrence_series = calculate_binary_occurrence_series


def calculate_binary_occurrence_at(
    history: HistoryInput, number: int, draw_index: int
) -> int:
    """Return ``Y_n(t)`` for one validated chronological draw index."""

    _validate_number(number)
    if type(draw_index) is not int or draw_index < 0:
        raise ValueError("draw_index must be a non-negative integer")
    try:
        if isinstance(history, Sequence):
            raw_draw = history[draw_index]
        else:
            raw_draw = tuple(islice(iter(history), draw_index + 1))[-1]
    except (IndexError, TypeError):
        raise ValueError("draw_index must be within history") from None
    return binary_occurrence(_validate_draw(raw_draw, draw_index), number)


binary_occurrence_at = calculate_binary_occurrence_at


def _validate_binary_label(label: int, index: int = 0) -> int:
    if type(label) is not int or label not in (0, 1):
        raise ValueError(f"binary label at index {index} must be exactly 0 or 1")
    return label


def _validated_labels(labels: Iterable[object]) -> BinarySeries:
    try:
        values = tuple(labels)
    except TypeError as error:
        raise ValueError("labels must be a finite binary sequence") from error
    return tuple(
        _validate_binary_label(cast(int, label), index)
        for index, label in enumerate(values)
    )


def extract_lag_features(labels: Sequence[int], outcome_index: int) -> tuple[int, ...]:
    """Return the six immediately preceding labels for an outcome index."""

    if type(outcome_index) is not int or outcome_index < LAG_DEPTH:
        raise ValueError(f"outcome_index must be at least {LAG_DEPTH}")
    if outcome_index > len(labels):
        raise ValueError("outcome_index must not exceed the available label length")
    return tuple(labels[outcome_index - lag] for lag in range(1, LAG_DEPTH + 1))


lag_features = extract_lag_features
extract_autoregressive_lags = extract_lag_features


def build_feature_vector(labels: Sequence[int], outcome_index: int) -> FeatureVector:
    """Build the seven-dimensional intercept-plus-own-lags feature vector."""

    lags = extract_lag_features(labels, outcome_index)
    return cast(FeatureVector, (1, *lags))


build_autoregressive_feature = build_feature_vector
build_autoregressive_feature_vector = build_feature_vector


def initial_weights() -> Weights:
    """Return a fresh exact initialization for one independent model."""

    return cast(Weights, (INITIAL_INTERCEPT, *INITIAL_LAG_WEIGHTS))


initialize_weights = initial_weights


def _exact_fraction(value: object, name: str) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if type(value) is int:
        return Fraction(value, 1)
    raise TypeError(f"{name} must use exact Fraction or integer arithmetic")


def _validated_weights(weights: Sequence[object]) -> Weights:
    if len(weights) != FEATURE_DIMENSION:
        raise ValueError(f"weights must contain exactly {FEATURE_DIMENSION} coordinates")
    converted = tuple(
        _exact_fraction(value, f"weights[{index}]")
        for index, value in enumerate(weights)
    )
    return cast(Weights, converted)


def _validated_features(features: Sequence[object]) -> FeatureVector:
    if len(features) != FEATURE_DIMENSION:
        raise ValueError(f"features must contain exactly {FEATURE_DIMENSION} coordinates")
    converted: list[int] = []
    for index, value in enumerate(features):
        if type(value) is not int or (index > 0 and value not in (0, 1)):
            raise ValueError("feature coordinates must be an intercept of 1 and binary lags")
        converted.append(value)
    if converted[0] != 1:
        raise ValueError("feature coordinate zero must be exactly one")
    return cast(FeatureVector, tuple(converted))


def raw_linear_score(weights: Sequence[object], features: Sequence[object]) -> Fraction:
    """Return the exact raw linear score before probability clipping."""

    theta = _validated_weights(weights)
    vector = _validated_features(features)
    return sum(
        (theta[index] * vector[index] for index in range(FEATURE_DIMENSION)),
        Fraction(0, 1),
    )


linear_raw_score = raw_linear_score


def clip_probability(value: object) -> Fraction:
    """Clip an exact rational score to the closed unit interval."""

    score = _exact_fraction(value, "probability")
    lower, upper = PREDICTION_CLIP
    if score < lower:
        return lower
    if score > upper:
        return upper
    return score


clip_01 = clip_probability


def predict_probability(weights: Sequence[object], features: Sequence[object]) -> Fraction:
    return clip_probability(raw_linear_score(weights, features))


predict = predict_probability


def brier_loss(prediction: object, label: int) -> Fraction:
    """Return the exact instantaneous squared probability error."""

    probability = clip_probability(prediction)
    outcome = _validate_binary_label(label)
    return (probability - outcome) ** 2


def online_delta_update(
    weights: Sequence[object], features: Sequence[object], label: int
) -> Weights:
    """Apply exactly one frozen delta update after the prediction is formed."""

    theta = _validated_weights(weights)
    vector = _validated_features(features)
    outcome = _validate_binary_label(label)
    prediction = clip_probability(raw_linear_score(theta, vector))
    error = Fraction(outcome, 1) - prediction
    updated = tuple(
        theta[index] + LEARNING_RATE * error * vector[index]
        for index in range(FEATURE_DIMENSION)
    )
    return cast(Weights, updated)


update_weights = online_delta_update
apply_online_update = online_delta_update


@dataclass(frozen=True, slots=True)
class OnlineUpdate:
    """Inspectable one-step causal prediction/update record."""

    PRE_UPDATE_WEIGHTS: Weights
    FEATURES: FeatureVector
    LABEL: int
    PREDICTION: Fraction
    ERROR: Fraction
    BRIER_LOSS: Fraction
    POST_UPDATE_WEIGHTS: Weights


def online_update_step(
    weights: Sequence[object], features: Sequence[object], label: int
) -> OnlineUpdate:
    """Return the prediction and post-label state for one causal update."""

    theta = _validated_weights(weights)
    vector = _validated_features(features)
    outcome = _validate_binary_label(label)
    prediction = clip_probability(raw_linear_score(theta, vector))
    error = Fraction(outcome, 1) - prediction
    post = cast(
        Weights,
        tuple(
            theta[index] + LEARNING_RATE * error * vector[index]
            for index in range(FEATURE_DIMENSION)
        ),
    )
    return OnlineUpdate(theta, vector, outcome, prediction, error, error**2, post)


def train_online_model(
    labels: Iterable[object],
    horizon: int,
    target_index: int | None = None,
) -> HorizonModel:
    """Train one number-specific model causally over one fixed horizon.

    ``labels`` contains chronological binary labels.  When ``target_index`` is
    supplied, only ``labels[:target_index]`` is read for training and target
    features, so a target outcome or future suffix cannot enter the model.
    """

    _validate_horizon(horizon)
    if target_index is None:
        prefix = _validated_labels(labels)
    else:
        _validate_target_index(target_index)
        if isinstance(labels, Sequence):
            raw_prefix = tuple(labels[:target_index])
        else:
            raw_prefix = tuple(islice(iter(labels), target_index))
        if len(raw_prefix) != target_index:
            raise ValueError("target_index must not exceed label length")
        prefix = _validated_labels(raw_prefix)

    target = len(prefix)
    minimum = horizon + LAG_DEPTH
    if target < minimum:
        raise InsufficientHistoryError(
            f"horizon {horizon} requires at least {minimum} labels including lag history"
        )

    start = target - horizon
    theta = initial_weights()
    initial = theta
    examples: list[int] = []
    features: list[FeatureVector] = []
    training_labels: list[int] = []
    predictions: list[Fraction] = []
    errors: list[Fraction] = []
    losses: list[Fraction] = []

    for outcome_index in range(start, target):
        vector = build_feature_vector(prefix, outcome_index)
        label = prefix[outcome_index]
        step = online_update_step(theta, vector, label)
        examples.append(outcome_index)
        features.append(vector)
        training_labels.append(label)
        predictions.append(step.PREDICTION)
        errors.append(step.ERROR)
        losses.append(step.BRIER_LOSS)
        theta = step.POST_UPDATE_WEIGHTS

    target_feature = build_feature_vector(prefix, target)
    target_raw = raw_linear_score(theta, target_feature)
    target_probability = clip_probability(target_raw)
    return HorizonModel(
        NUMBER=0,
        HORIZON=horizon,
        TRAINING_START=start,
        TRAINING_END_EXCLUSIVE=target,
        INITIAL_WEIGHTS=initial,
        WEIGHTS=theta,
        TARGET_FEATURE=target_feature,
        TARGET_RAW_SCORE=target_raw,
        TARGET_PROBABILITY=target_probability,
        TRAINING_EXAMPLES=tuple(examples),
        TRAINING_FEATURES=tuple(features),
        TRAINING_LABELS=tuple(training_labels),
        TRAINING_PREDICTIONS=tuple(predictions),
        TRAINING_ERRORS=tuple(errors),
        BRIER_LOSSES=tuple(losses),
    )


train_model = train_online_model
fit_online_model = train_online_model


def _labels_for_number(prior_history: tuple[HistoryDraw, ...], number: int) -> BinarySeries:
    return tuple(int(number in draw) for draw in prior_history)


def train_number_horizon_model(
    prior_history: tuple[HistoryDraw, ...], number: int, horizon: int
) -> HorizonModel:
    """Train one number/horizon model from an already validated prefix."""

    _validate_number(number)
    _validate_horizon(horizon)
    model = train_online_model(_labels_for_number(prior_history, number), horizon)
    return HorizonModel(
        NUMBER=number,
        HORIZON=model.HORIZON,
        TRAINING_START=model.TRAINING_START,
        TRAINING_END_EXCLUSIVE=model.TRAINING_END_EXCLUSIVE,
        INITIAL_WEIGHTS=model.INITIAL_WEIGHTS,
        WEIGHTS=model.WEIGHTS,
        TARGET_FEATURE=model.TARGET_FEATURE,
        TARGET_RAW_SCORE=model.TARGET_RAW_SCORE,
        TARGET_PROBABILITY=model.TARGET_PROBABILITY,
        TRAINING_EXAMPLES=model.TRAINING_EXAMPLES,
        TRAINING_FEATURES=model.TRAINING_FEATURES,
        TRAINING_LABELS=model.TRAINING_LABELS,
        TRAINING_PREDICTIONS=model.TRAINING_PREDICTIONS,
        TRAINING_ERRORS=model.TRAINING_ERRORS,
        BRIER_LOSSES=model.BRIER_LOSSES,
    )


train_model_for_number = train_number_horizon_model
fit_number_horizon_model = train_number_horizon_model


def train_number_models(
    prior_history: tuple[HistoryDraw, ...], number: int
) -> tuple[HorizonModel, HorizonModel, HorizonModel]:
    _validate_number(number)
    return cast(
        tuple[HorizonModel, HorizonModel, HorizonModel],
        tuple(
            train_number_horizon_model(prior_history, number, horizon)
            for horizon in TRAINING_HORIZONS
        ),
    )


@lru_cache(maxsize=32)
def _rank_validated_horizon(
    prior_history: tuple[HistoryDraw, ...], horizon: int
) -> HorizonRanking:
    _validate_horizon(horizon)
    if len(prior_history) < horizon + LAG_DEPTH:
        raise InsufficientHistoryError(
            f"horizon {horizon} requires at least {horizon + LAG_DEPTH} prior draws"
        )

    models = tuple(
        train_number_horizon_model(prior_history, number, horizon)
        for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1)
    )
    probabilities = tuple(model.TARGET_PROBABILITY for model in models)
    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-probabilities[number - 1], number),
        )
    )
    positions = [0] * (NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1)
    normalized_ranks: list[Fraction] = [Fraction(0, 1)] * len(positions)
    for position, number in enumerate(ordered_numbers, start=1):
        positions[number - 1] = position
        normalized_ranks[number - 1] = Fraction(49 - position, 48)

    return HorizonRanking(
        HORIZON=horizon,
        TARGET_PROBABILITIES=probabilities,
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized_ranks),
        MODELS=models,
    )


def rank_numbers_by_horizon(
    history: HistoryInput, target_index: int, horizon: int
) -> HorizonRanking:
    """Rank all numbers by one exact target-probability horizon."""

    return _rank_validated_horizon(validate_prior_history(history, target_index), horizon)


rank_numbers_by_window = rank_numbers_by_horizon
calculate_horizon_ranking = rank_numbers_by_horizon
calculate_window_ranking = rank_numbers_by_horizon


def calculate_horizon_rankings(
    history: HistoryInput, target_index: int, horizon: int | None = None
) -> HorizonRanking | tuple[HorizonRanking, HorizonRanking, HorizonRanking]:
    """Return one requested ranking or all three fixed horizon rankings."""

    prior_history = validate_prior_history(history, target_index)
    if horizon is not None:
        return _rank_validated_horizon(prior_history, horizon)
    return cast(
        tuple[HorizonRanking, HorizonRanking, HorizonRanking],
        tuple(_rank_validated_horizon(prior_history, current) for current in TRAINING_HORIZONS),
    )


calculate_window_rankings = calculate_horizon_rankings


def fuse_horizon_rankings(
    rankings: tuple[HorizonRanking, HorizonRanking, HorizonRanking]
) -> FusedNumberRanking:
    """Fuse 50/300/750 normalized rankings with exact equal weights."""

    if len(rankings) != len(TRAINING_HORIZONS):
        raise ValueError("exactly three horizon rankings required for fusion")
    if tuple(ranking.HORIZON for ranking in rankings) != TRAINING_HORIZONS:
        raise ValueError(f"horizon rankings must correspond to {TRAINING_HORIZONS}")

    mean_ranks: list[Fraction] = []
    robustness: list[RobustnessTuple] = []
    for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1):
        normalized = tuple(ranking.normalized_rank(number) for ranking in rankings)
        mean_ranks.append(sum(normalized, Fraction(0, 1)) / 3)
        robustness.append(cast(RobustnessTuple, tuple(sorted(normalized))))

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
        MEAN_ML_RANK=tuple(mean_ranks),
        ROBUSTNESS=tuple(robustness),
        HORIZON_RANKINGS=rankings,
    )


fuse_window_rankings = fuse_horizon_rankings
fuse_rankings = fuse_horizon_rankings


def calculate_fused_number_ranking(
    history: HistoryInput, target_index: int
) -> FusedNumberRanking:
    """Calculate the complete causal 50/300/750 fused ranking."""

    prior_history = validate_prior_history(history, target_index)
    rankings = cast(
        tuple[HorizonRanking, HorizonRanking, HorizonRanking],
        tuple(_rank_validated_horizon(prior_history, horizon) for horizon in TRAINING_HORIZONS),
    )
    return fuse_horizon_rankings(rankings)


def produce_b649_multiscale_online_brier_ar6_ranked_pool_v1(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce the ordered 210-ticket AR6 source universe."""

    fused = calculate_fused_number_ranking(history, target_index)
    top10 = fused.TOP_NUMBERS
    if len(top10) != TOP_NUMBER_COUNT:
        raise RuntimeError("fused ranking did not produce exactly ten top numbers")

    tickets: list[Ticket] = []
    for rank_positions in combinations(range(TOP_NUMBER_COUNT), PICK_COUNT):
        ticket = cast(Ticket, tuple(sorted(top10[position] for position in rank_positions)))
        tickets.append(ticket)

    source_tickets = tuple(tickets)
    if len(source_tickets) != SOURCE_CANDIDATE_TICKET_COUNT:
        raise RuntimeError(
            f"source universe produced {len(source_tickets)} tickets, expected "
            f"{SOURCE_CANDIDATE_TICKET_COUNT}"
        )
    if len(set(source_tickets)) != SOURCE_CANDIDATE_TICKET_COUNT:
        raise RuntimeError("source universe produced duplicate tickets")
    return source_tickets


produce_source_ticket_universe = produce_b649_multiscale_online_brier_ar6_ranked_pool_v1
build_source_ticket_universe = produce_b649_multiscale_online_brier_ar6_ranked_pool_v1
produce_b649_multiscale_online_brier_ar6_ranked_pool = (
    produce_b649_multiscale_online_brier_ar6_ranked_pool_v1
)


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
    """Return sorted-key compact UTF-8 JSON for one complete semantic record."""

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
    return canonicalize_semantic_record(record).decode("utf-8")


def signature_hash_for_semantics(record: Mapping[str, object]) -> str:
    return hashlib.sha256(canonicalize_semantic_record(record)).hexdigest()


def candidate_id_for_semantics(record: Mapping[str, object]) -> str:
    return f"BMSGV1_ML_{signature_hash_for_semantics(record)[:16]}"


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """Deterministic identity material for one frozen ML hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    canonical_json = canonical_semantic_json(record)
    signature_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return CandidateIdentity(
        CANDIDATE_ID=f"BMSGV1_ML_{signature_hash[:16]}",
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
        "produce_b649_multiscale_online_brier_ar6_multiticket_"
        f"{_CONSTRUCTOR_SYMBOL_SLUGS[constructor_id]}_v1_k{ticket_count}"
    )


def _candidate_semantic_record(
    constructor_id: str, ticket_count: int
) -> dict[str, object]:
    constructor_metadata = _constructors.CONSTRUCTOR_METADATA[constructor_id]
    return {
        "ARITHMETIC": ARITHMETIC,
        "AUTOREGRESSIVE_LAG_DEPTH": AUTOREGRESSIVE_LAG_DEPTH,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNEL": (
            _CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS[constructor_id]
        ),
        "CONSTRUCTOR_ID": constructor_id,
        "CONSTRUCTOR_VERSION": constructor_metadata.VERSION,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FEATURE_DIMENSION": FEATURE_DIMENSION,
        "FEATURE_RULE": FEATURE_RULE,
        "FEATURE_SELECTION": FEATURE_SELECTION,
        "HISTORY_ORDER": HISTORY_ORDER,
        "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
        "INITIAL_INTERCEPT": INITIAL_INTERCEPT,
        "INITIAL_LAG_WEIGHTS": INITIAL_LAG_WEIGHTS,
        "INITIALIZATION_RULE": INITIALIZATION_RULE,
        "LEARNING_RATE": LEARNING_RATE,
        "LOSS_FAMILY": LOSS_FAMILY,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "MODEL_CLASS": MODEL_CLASS,
        "NATIVE_TICKET_COUNT": ticket_count,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "OFFICIAL_NULL_P0": OFFICIAL_NULL_P0,
        "ONLINE_UPDATE_RULE": ONLINE_UPDATE_RULE,
        "OUTPUT_SHAPE": OUTPUT_SHAPE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PER_HORIZON_RANKING_RULE": PER_HORIZON_RANKING_RULE,
        "PICK_COUNT": PICK_COUNT,
        "PREDICTION_CLIP": PREDICTION_CLIP,
        "PREDICTION_RULE": PREDICTION_RULE,
        "RAW_SCORE_RULE": RAW_SCORE_RULE,
        "RNG": None,
        "RNG_SEED": None,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_NUMBER_POOL_COUNT": SOURCE_NUMBER_POOL_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "TARGET_OUTCOME_USED": TARGET_OUTCOME_USED,
        "TARGET_RULE": TARGET_RULE,
        "TICKET_COUNT": ticket_count,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
        "TRAINING_HORIZONS": TRAINING_HORIZONS,
        "TRAINING_RULE": TRAINING_RULE,
        "WINDOWS": WINDOWS,
        "WINDOW_FUSION_RULE": WINDOW_FUSION_RULE,
        "WINDOW_NORMALIZATION_RULE": WINDOW_NORMALIZATION_RULE,
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
                raise RuntimeError("candidate ID collision in frozen ML hypothesis matrix")
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
        raise RuntimeError("candidate signature collision in frozen ML hypothesis matrix")
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
CANDIDATE_SIGNATURE_HASHES: Final[Mapping[str, str]] = MappingProxyType(
    {
        metadata.CANDIDATE_ID: metadata.SIGNATURE_HASH
        for metadata in CANDIDATE_AUTHORITIES
    }
)


def candidate_id_for(constructor_id: str, ticket_count: int) -> str:
    """Return the frozen candidate ID for one constructor/budget pair."""

    try:
        return CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT[(constructor_id, ticket_count)]
    except KeyError as error:
        raise KeyError(
            f"unknown constructor/ticket_count pair: {(constructor_id, ticket_count)}"
        ) from error


def _produce_named_candidate(
    constructor_id: str,
    ticket_count: int,
    history: HistoryInput,
    target_index: int,
) -> TicketPortfolio:
    source_tickets = produce_source_ticket_universe(history, target_index)
    if constructor_id == "B649_CANDIDATE_SET_LOW_OVERLAP_V1":
        return _constructors.construct_b649_candidate_set_low_overlap_v1(
            source_tickets, ticket_count
        )
    if constructor_id == "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1":
        return _constructors.construct_b649_candidate_set_exposure_balanced_v1(
            source_tickets, ticket_count
        )
    if constructor_id == "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1":
        return _constructors.construct_b649_candidate_set_hybrid_diversity_v1(
            source_tickets, ticket_count
        )
    raise KeyError(f"unknown constructor ID: {constructor_id}")


def produce_candidate_portfolio(
    candidate_id: str, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce one of the nine frozen candidate portfolios."""

    try:
        metadata = CANDIDATE_METADATA[candidate_id]
    except KeyError as error:
        raise KeyError(f"unknown candidate ID: {candidate_id}") from error
    return _produce_named_candidate(
        metadata.CONSTRUCTOR_ID, metadata.TICKET_COUNT, history, target_index
    )


produce_biglotto_multi_ticket_candidate = produce_candidate_portfolio
produce_multi_ticket_candidate = produce_candidate_portfolio
produce_b649_multiscale_online_brier_ar6_multi_ticket_candidate = produce_candidate_portfolio


def produce_b649_multiscale_online_brier_ar6_multiticket_low_overlap_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 5, history, target_index)


def produce_b649_multiscale_online_brier_ar6_multiticket_low_overlap_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 10, history, target_index)


def produce_b649_multiscale_online_brier_ar6_multiticket_low_overlap_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[0], 20, history, target_index)


def produce_b649_multiscale_online_brier_ar6_multiticket_exposure_balanced_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 5, history, target_index)


def produce_b649_multiscale_online_brier_ar6_multiticket_exposure_balanced_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 10, history, target_index)


def produce_b649_multiscale_online_brier_ar6_multiticket_exposure_balanced_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[1], 20, history, target_index)


def produce_b649_multiscale_online_brier_ar6_multiticket_hybrid_diversity_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 5, history, target_index)


def produce_b649_multiscale_online_brier_ar6_multiticket_hybrid_diversity_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 10, history, target_index)


def produce_b649_multiscale_online_brier_ar6_multiticket_hybrid_diversity_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(CONSTRUCTOR_IDS[2], 20, history, target_index)


produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_low_overlap_v1_k5 = (
    produce_b649_multiscale_online_brier_ar6_multiticket_low_overlap_v1_k5
)
produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_low_overlap_v1_k10 = (
    produce_b649_multiscale_online_brier_ar6_multiticket_low_overlap_v1_k10
)
produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_low_overlap_v1_k20 = (
    produce_b649_multiscale_online_brier_ar6_multiticket_low_overlap_v1_k20
)
produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_exposure_balanced_v1_k5 = (
    produce_b649_multiscale_online_brier_ar6_multiticket_exposure_balanced_v1_k5
)
produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_exposure_balanced_v1_k10 = (
    produce_b649_multiscale_online_brier_ar6_multiticket_exposure_balanced_v1_k10
)
produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_exposure_balanced_v1_k20 = (
    produce_b649_multiscale_online_brier_ar6_multiticket_exposure_balanced_v1_k20
)
produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_hybrid_diversity_v1_k5 = (
    produce_b649_multiscale_online_brier_ar6_multiticket_hybrid_diversity_v1_k5
)
produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_hybrid_diversity_v1_k10 = (
    produce_b649_multiscale_online_brier_ar6_multiticket_hybrid_diversity_v1_k10
)
produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_hybrid_diversity_v1_k20 = (
    produce_b649_multiscale_online_brier_ar6_multiticket_hybrid_diversity_v1_k20
)


__all__ = [
    "ARITHMETIC",
    "AR_LAG_DEPTH",
    "AUTOREGRESSIVE_LAG_DEPTH",
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
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "FEATURE_DIMENSION",
    "FEATURE_RULE",
    "FEATURE_SELECTION",
    "HISTORY_ORDER",
    "HORIZONS",
    "HYPOTHESIS_VERSION",
    "INITIALIZATION_RULE",
    "INITIAL_INTERCEPT",
    "INITIAL_LAG_WEIGHTS",
    "LAG_DEPTH",
    "LEARNING_RATE",
    "LOSS_FAMILY",
    "LOTTERY_TYPE",
    "METHOD_FAMILY",
    "MINIMUM_HISTORY",
    "MODEL_CLASS",
    "NUMBER_DOMAIN",
    "OUTPUT_SHAPE",
    "P0",
    "PARAMETER_SELECTION_RULE",
    "PER_HORIZON_RANKING_RULE",
    "PICK_COUNT",
    "PREDICTION_CLIP",
    "PREDICTION_CLIP_RULE",
    "RNG",
    "RNG_SEMANTICS",
    "ROBUSTNESS_RULE",
    "SOURCE_CANDIDATE_TICKET_COUNT",
    "SOURCE_NUMBER_POOL_COUNT",
    "SOURCE_TICKET_ORDER",
    "SOURCE_UNIVERSE_CONTRACT",
    "SOURCE_UNIVERSE_ID",
    "SOURCE_UNIVERSE_METADATA",
    "SOURCE_UNIVERSE_VERSION",
    "SOURCE_WINDOWS",
    "TARGET_OUTCOME_USED",
    "TARGET_RULE",
    "TICKET_COUNTS",
    "TOP_NUMBER_COUNT",
    "TRAINING_HORIZONS",
    "TRAINING_RULE",
    "WINDOWS",
    "WINDOW_FUSION_RULE",
    "WINDOW_NORMALIZATION_RULE",
    "FusedNumberRanking",
    "FusedRanking",
    "InsufficientHistoryError",
    "OnlineLinearProbabilityModel",
    "OnlineModel",
    "OnlineUpdate",
    "Ticket",
    "TicketPortfolio",
    "binary_occurrence",
    "binary_occurrence_at",
    "binary_occurrence_series",
    "brier_loss",
    "build_autoregressive_feature",
    "build_autoregressive_feature_vector",
    "build_feature_vector",
    "build_source_ticket_universe",
    "calculate_binary_occurrence_at",
    "calculate_binary_occurrence_series",
    "calculate_fused_number_ranking",
    "calculate_horizon_ranking",
    "calculate_horizon_rankings",
    "calculate_occurrence_series",
    "calculate_window_ranking",
    "calculate_window_rankings",
    "candidate_id_for",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "clip_01",
    "clip_probability",
    "derive_candidate_identity",
    "extract_autoregressive_lags",
    "extract_lag_features",
    "fit_number_horizon_model",
    "fit_online_model",
    "fuse_horizon_rankings",
    "fuse_rankings",
    "fuse_window_rankings",
    "initial_weights",
    "initialize_weights",
    "lag_features",
    "linear_raw_score",
    "occurrence_label",
    "online_delta_update",
    "online_update_step",
    "predict",
    "predict_probability",
    "produce_b649_multiscale_online_brier_ar6_multi_ticket_candidate",
    "produce_b649_multiscale_online_brier_ar6_multiticket_exposure_balanced_v1_k5",
    "produce_b649_multiscale_online_brier_ar6_multiticket_exposure_balanced_v1_k10",
    "produce_b649_multiscale_online_brier_ar6_multiticket_exposure_balanced_v1_k20",
    "produce_b649_multiscale_online_brier_ar6_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_multiscale_online_brier_ar6_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_multiscale_online_brier_ar6_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_multiscale_online_brier_ar6_multiticket_low_overlap_v1_k5",
    "produce_b649_multiscale_online_brier_ar6_multiticket_low_overlap_v1_k10",
    "produce_b649_multiscale_online_brier_ar6_multiticket_low_overlap_v1_k20",
    "produce_b649_multiscale_online_brier_ar6_ranked_pool",
    "produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_exposure_balanced_v1_k5",
    "produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_exposure_balanced_v1_k10",
    "produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_exposure_balanced_v1_k20",
    "produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_low_overlap_v1_k5",
    "produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_low_overlap_v1_k10",
    "produce_b649_multiscale_online_brier_ar6_ranked_pool_multiticket_low_overlap_v1_k20",
    "produce_b649_multiscale_online_brier_ar6_ranked_pool_v1",
    "produce_biglotto_multi_ticket_candidate",
    "produce_brier_ar6_candidate_portfolio",
    "produce_candidate_portfolio",
    "produce_multi_ticket_candidate",
    "produce_source_ticket_universe",
    "rank_numbers_by_horizon",
    "rank_numbers_by_window",
    "raw_linear_score",
    "signature_hash_for_semantics",
    "train_model",
    "train_model_for_number",
    "train_number_horizon_model",
    "train_number_models",
    "train_online_model",
    "update_weights",
    "validate_history",
    "validate_prior_history",
]


produce_brier_ar6_candidate_portfolio = produce_candidate_portfolio
