"""Causal deterministic BigLotto Level-2 pairwise candidate batch R1.

This module freezes exactly one candidate from the completed design authority
``BMSGV1_L2_PAIRWISE_798bb953e431872b``.  It combines the frozen 300-window
spectral inverse-participation-ratio component with the frozen 300-example
online AR6 target-probability component using an identity-normalized exact
one-half plus one-half score.  All 49 legal numbers are ranked directly and
the first six ranked numbers form one native ticket.

The implementation is history-only, exact-rational, deterministic, and
research-only.  It has no outcome tuning, randomness, I/O, database access,
network access, replay, catalog registration, or registry wiring.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import islice, pairwise
from types import MappingProxyType
from typing import Final, cast

from lottolab.research import (
    biglotto_multiscale_online_brier_ar6_multi_ticket_candidate_batch_r1 as _ml_parent,
)
from lottolab.research import (
    biglotto_multiscale_spectral_concentration_multi_ticket_candidate_batch_r1 as _spectral_parent,
)

type Ticket = tuple[int, int, int, int, int, int]
type TicketPortfolio = tuple[Ticket, ...]
type HistoryDraw = tuple[int, int, int, int, int, int]
type HistoryInput = Sequence[object] | Iterable[object]
type Components = tuple[Fraction, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
CANDIDATE_ID: Final[str] = "BMSGV1_L2_PAIRWISE_798bb953e431872b"
SELECTED_GAP_ID: Final[str] = CANDIDATE_ID
DESIGN_ID: Final[str] = "B649_PAIRWISE_SPECTRAL_ML_WEIGHTED_SCORE_300_V1"
DESIGN_SIGNATURE_SHA256: Final[str] = (
    "5395a02d5463eeb542e09694f8a74ca205f120c62168edefee311f24090ac434"
)
SOURCE_UNIVERSE_ID: Final[str] = DESIGN_ID
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"
FEATURE_1: Final[str] = "SIGNAL_FOURIER"
FEATURE_2: Final[str] = "ML_LIKE"
METHOD_FAMILY: Final[str] = "PAIRWISE_FUSION"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
WINDOW: Final[int] = 300
SPECTRAL_WINDOW: Final[int] = WINDOW
ML_HORIZON: Final[int] = WINDOW
MINIMUM_HISTORY: Final[int] = WINDOW + 6
SPECTRAL_PARENT_ID: Final[str] = "B649_MULTISCALE_SPECTRAL_IPR_RANKED_POOL_V1"
SPECTRAL_PARENT_COMMIT: Final[str] = "68fc74e3d5b1819e3a551572cc838a32f4c66b27"
ML_PARENT_ID: Final[str] = "B649_MULTISCALE_ONLINE_BRIER_AR6_RANKED_POOL_V1"
ML_PARENT_COMMIT: Final[str] = "5724501332ecdebb910be56113738ae282d8c531"
COMPONENT_NORMALIZATION: Final[str] = "IDENTITY"
SPECTRAL_WEIGHT: Final[Fraction] = Fraction(1, 2)
ML_WEIGHT: Final[Fraction] = Fraction(1, 2)
SPECTRAL_WEIGHT_TEXT: Final[str] = "1/2"
ML_WEIGHT_TEXT: Final[str] = "1/2"
PAIRWISE_SCORE_RULE: Final[str] = (
    "PAIRWISE_SCORE(n)=(SPECTRAL_IPR_300(n)+TARGET_PROBABILITY_300(n))/2;EXACT_RATIONAL"
)
NUMBER_RANKING_RULE: Final[str] = "PAIRWISE_SCORE_DESC_NUMBER_ASC"
RANKED_POOL_DOMAIN: Final[str] = "1..49"
RANKED_POOL_CARDINALITY: Final[int] = 49
RANKED_POOL_RULE: Final[str] = "ALL_49_LEGAL_NUMBERS;NO_TOP10_INTERMEDIATE_POOL"
TICKET_SELECTION_RULE: Final[str] = "FIRST_6_RANKED_NUMBERS"
TICKET_CONSTRUCTION_RULE: Final[str] = (
    "RANKED_POSITIONS_1..6;MAP_TO_NUMBERS;SORT_ASCENDING;SINGLE_NATIVE_TICKET"
)
NATIVE_TICKET_COUNT: Final[int] = 1
CAUSAL_CUTOFF_RULE: Final[str] = (
    "SPECTRAL_HISTORY=history[T-300:T];ML_EXAMPLES=t=T-300,...,T-1;"
    "TARGET_OUTCOME=Y(T)_NEVER_USED;FUTURE_SUFFIX=NEVER_USED"
)
PARAMETER_SELECTION_RULE: Final[str] = "FIXED_STRUCTURAL_SYMMETRIC_NO_OUTCOME_TUNING"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
RNG: Final[None] = None
FLOATING_FFT_USED_FOR_RANKING: Final[str] = "NO"
LAST_HIT_GAP_USED: Final[str] = "NO"
DOMINANT_PERIOD_USED_FOR_PRIMARY_SCORE: Final[str] = "NO"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "BALANCED_FUSION_OF_FULL_SPECTRUM_TEMPORAL_STRUCTURE_AND_CAUSAL_ONLINE_SHORT_MEMORY_PROBABILITY"
)
SPECTRAL_COMPONENT_RULE: Final[str] = "SPECTRAL_COMPONENT(n)=SPECTRAL_IPR_300(n)"
ML_COMPONENT_RULE: Final[str] = "ML_COMPONENT(n)=TARGET_PROBABILITY_300(n)"
SPECTRAL_FORMULA: Final[str] = (
    "R(0)>0=>SUM_l(R(l)^2)/(W*R(0)^2);R(0)=0=>0;EXACT_RATIONAL"
)
SPECTRAL_PRESERVATION_RULES: Final[tuple[str, ...]] = (
    "EXACT_RATIONAL_BINARY_APPEARANCE_PROCESS",
    "EXACT_MEAN_CENTERING",
    "EXACT_CIRCULAR_AUTOCORRELATION",
    "PARSEVAL_WIENER_KHINCHIN_FULL_SPECTRUM_IPR",
    "NO_FLOATING_FFT_RANKING",
    "NO_LAST_HIT_GAP",
    "NO_DOMINANT_PERIOD_GAP_SCORING",
)
ML_PRESERVATION_RULES: Final[tuple[str, ...]] = (
    "OWN_NUMBER_AR6_BINARY_LAGS",
    "FEATURES=(1,Y(t-1),...,Y(t-6))",
    "INITIAL_WEIGHTS=(6/49,0,0,0,0,0,0)",
    "LEARNING_RATE=1/64",
    "CHRONOLOGICAL_SINGLE_PASS",
    "EXACT_FRACTION_ARITHMETIC",
    "CLIP_01",
    "NO_CROSS_NUMBER_FEATURES",
    "NO_HYPERPARAMETER_TUNING",
)
IMPLEMENTATION_MODULE: Final[str] = (
    "lottolab.research.biglotto_l2_pairwise_signal_fourier_ml_like_weighted_score_candidate_batch_r1"
)
IMPLEMENTATION_SYMBOL: Final[str] = (
    "produce_bmsgv1_l2_pairwise_signal_fourier_ml_like_weighted_score_candidate_batch_r1"
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than 306 strictly prior draws are available."""


@dataclass(frozen=True, slots=True)
class PairwiseNumberScore:
    """One exact fused score and its two parent contributions."""

    NUMBER: int
    SPECTRAL_COMPONENT: Fraction
    ML_COMPONENT: Fraction
    PAIRWISE_SCORE: Fraction
    POSITION: int

    @property
    def SPECTRAL_IPR_300(self) -> Fraction:
        return self.SPECTRAL_COMPONENT

    @property
    def TARGET_PROBABILITY_300(self) -> Fraction:
        return self.ML_COMPONENT


@dataclass(frozen=True, slots=True)
class PairwiseRanking:
    """All 49 ranked numbers and the single native ticket."""

    SPECTRAL_COMPONENTS: Components
    ML_COMPONENTS: Components
    PAIRWISE_SCORES: Components
    RANKED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    SCORES: tuple[PairwiseNumberScore, ...]
    NATIVE_TICKET: Ticket

    @property
    def ORDERED_NUMBERS(self) -> tuple[int, ...]:
        return self.RANKED_NUMBERS

    @property
    def TICKET(self) -> Ticket:
        return self.NATIVE_TICKET

    @property
    def TICKETS(self) -> TicketPortfolio:
        return (self.NATIVE_TICKET,)

    @property
    def NATIVE_TICKETS(self) -> TicketPortfolio:
        return self.TICKETS

    def spectral_component(self, number: int) -> Fraction:
        _validate_number(number)
        return self.SPECTRAL_COMPONENTS[number - 1]

    def ml_component(self, number: int) -> Fraction:
        _validate_number(number)
        return self.ML_COMPONENTS[number - 1]

    def pairwise_score(self, number: int) -> Fraction:
        _validate_number(number)
        return self.PAIRWISE_SCORES[number - 1]

    def score(self, number: int) -> Fraction:
        return self.pairwise_score(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def score_record(self, number: int) -> PairwiseNumberScore:
        return self.SCORES[self.position(number) - 1]


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """The selected-gap identity and completed-design signature."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


@dataclass(frozen=True, slots=True)
class CandidateMetadata:
    """Immutable metadata for the one frozen pairwise candidate."""

    CANDIDATE_ID: str
    SELECTED_GAP_ID: str
    DESIGN_ID: str
    DESIGN_SIGNATURE_SHA256: str
    FEATURE_1: str
    FEATURE_2: str
    WINDOW: int
    COMPONENT_NORMALIZATION: str
    SPECTRAL_WEIGHT: str
    ML_WEIGHT: str
    IMPLEMENTATION_MODULE: str
    IMPLEMENTATION_SYMBOL: str
    NATIVE_TICKET_COUNT: int
    MINIMUM_HISTORY: int
    DETERMINISM_CLASS: str
    SEMANTICS: Mapping[str, object]


SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = MappingProxyType(
    {
        "AUTHORITY_TYPE": "PREDICTION_PRODUCING_V1_DESIGN_AUTHORITY",
        "CANDIDATE_CONSTRUCTION": "RANKED_POOL",
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "COMPONENT_NORMALIZATION": COMPONENT_NORMALIZATION,
        "DESIGN_ID": DESIGN_ID,
        "DESIGN_SIGNATURE_SHA256": DESIGN_SIGNATURE_SHA256,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "FEATURE_1": FEATURE_1,
        "FEATURE_2": FEATURE_2,
        "FUSION": "WEIGHTED_SCORE",
        "HISTORY_ORDER": HISTORY_ORDER,
        "IMPLEMENTATION_READY": "YES",
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "ML_COMPONENT_RULE": ML_COMPONENT_RULE,
        "ML_HORIZON": ML_HORIZON,
        "ML_PARENT_COMMIT": ML_PARENT_COMMIT,
        "ML_PARENT_ID": ML_PARENT_ID,
        "ML_PRESERVATION_RULES": ML_PRESERVATION_RULES,
        "ML_WEIGHT": ML_WEIGHT_TEXT,
        "NATIVE_TICKET_COUNT": NATIVE_TICKET_COUNT,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "NUMBER_RANKING_RULE": NUMBER_RANKING_RULE,
        "PAIRWISE_SCORE_RULE": PAIRWISE_SCORE_RULE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PICK_COUNT": PICK_COUNT,
        "RANKED_POOL_CARDINALITY": RANKED_POOL_CARDINALITY,
        "RANKED_POOL_DOMAIN": RANKED_POOL_DOMAIN,
        "RANKED_POOL_RULE": RANKED_POOL_RULE,
        "RNG": RNG_SEMANTICS,
        "SELECTED_GAP_ID": SELECTED_GAP_ID,
        "SPECTRAL_COMPONENT_RULE": SPECTRAL_COMPONENT_RULE,
        "SPECTRAL_FORMULA": SPECTRAL_FORMULA,
        "SPECTRAL_PARENT_COMMIT": SPECTRAL_PARENT_COMMIT,
        "SPECTRAL_PARENT_ID": SPECTRAL_PARENT_ID,
        "SPECTRAL_PRESERVATION_RULES": SPECTRAL_PRESERVATION_RULES,
        "SPECTRAL_WEIGHT": SPECTRAL_WEIGHT_TEXT,
        "SPECTRAL_WINDOW": SPECTRAL_WINDOW,
        "TICKET_CONSTRUCTION": "SINGLE_TICKET",
        "TICKET_CONSTRUCTION_RULE": TICKET_CONSTRUCTION_RULE,
        "TICKET_SELECTION_RULE": TICKET_SELECTION_RULE,
        "WINDOW": WINDOW,
    }
)


CANDIDATE_SEMANTICS: Final[Mapping[str, object]] = MappingProxyType(
    {
        "CANDIDATE_ID": CANDIDATE_ID,
        "COMPONENT_NORMALIZATION": COMPONENT_NORMALIZATION,
        "DESIGN_ID": DESIGN_ID,
        "DESIGN_SIGNATURE_SHA256": DESIGN_SIGNATURE_SHA256,
        "FEATURE_1": FEATURE_1,
        "FEATURE_2": FEATURE_2,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "ML_COMPONENT_RULE": ML_COMPONENT_RULE,
        "ML_PARENT_ID": ML_PARENT_ID,
        "ML_PARENT_COMMIT": ML_PARENT_COMMIT,
        "ML_WEIGHT": ML_WEIGHT_TEXT,
        "NATIVE_TICKET_COUNT": NATIVE_TICKET_COUNT,
        "NUMBER_RANKING_RULE": NUMBER_RANKING_RULE,
        "PAIRWISE_SCORE_RULE": PAIRWISE_SCORE_RULE,
        "RANKED_POOL_CARDINALITY": RANKED_POOL_CARDINALITY,
        "SELECTED_GAP_ID": SELECTED_GAP_ID,
        "SPECTRAL_COMPONENT_RULE": SPECTRAL_COMPONENT_RULE,
        "SPECTRAL_PARENT_COMMIT": SPECTRAL_PARENT_COMMIT,
        "SPECTRAL_PARENT_ID": SPECTRAL_PARENT_ID,
        "SPECTRAL_WEIGHT": SPECTRAL_WEIGHT_TEXT,
        "TICKET_CONSTRUCTION_RULE": TICKET_CONSTRUCTION_RULE,
        "TICKET_SELECTION_RULE": TICKET_SELECTION_RULE,
        "WINDOW": WINDOW,
    }
)


def _validate_number(number: int) -> None:
    if type(number) is not int or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]:
        raise ValueError("number must be an integer in 1..49")


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
        values = tuple(cast(Iterable[object], raw_draw))
    except TypeError as error:
        raise ValueError(f"history[{draw_index}] must contain exactly six integers") from error

    if len(values) != PICK_COUNT:
        raise ValueError(f"history[{draw_index}] must contain exactly six numbers")

    numbers: list[int] = []
    for position, raw_number in enumerate(values):
        if type(raw_number) is not int:
            raise ValueError(f"history[{draw_index}][{position}] must be an integer")
        if not NUMBER_DOMAIN[0] <= raw_number <= NUMBER_DOMAIN[1]:
            raise ValueError(f"history[{draw_index}][{position}] must be in 1..49")
        numbers.append(raw_number)

    sorted_numbers = tuple(sorted(numbers))
    for left, right in pairwise(sorted_numbers):
        if left == right:
            raise ValueError(f"history[{draw_index}] contains duplicate number {left}")
    return cast(HistoryDraw, sorted_numbers)


def validate_prior_history(history: HistoryInput, target_index: int) -> tuple[HistoryDraw, ...]:
    """Validate exactly the strictly prior prefix required by the candidate."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"target_index {target_index} provides {len(raw_prefix)} prior draws; "
            f"required minimum {MINIMUM_HISTORY}"
        )
    return tuple(_validate_draw(raw_draw, index) for index, raw_draw in enumerate(raw_prefix))


validate_history = validate_prior_history


def _binary_circular_autocorrelation(appearance: tuple[int, ...]) -> tuple[Fraction, ...]:
    """Return the parent spectral autocorrelation identity exactly."""

    occurrence_count = sum(appearance)
    positions = tuple(index for index, value in enumerate(appearance) if value == 1)
    lag_counts = [0] * WINDOW
    for left in positions:
        for right in positions:
            lag_counts[(right - left) % WINDOW] += 1
    centered_offset = Fraction(occurrence_count * occurrence_count, WINDOW)
    return tuple(Fraction(count, 1) - centered_offset for count in lag_counts)


def _spectral_component_from_window(window_draws: Sequence[HistoryDraw], number: int) -> Fraction:
    _validate_number(number)
    appearance = tuple(1 if number in draw else 0 for draw in window_draws)
    if len(appearance) != WINDOW:
        raise ValueError(f"spectral window must contain exactly {WINDOW} draws")
    centered = _spectral_parent.mean_centered_binary_series(appearance)
    if sum(centered, Fraction(0, 1)) != 0:
        raise RuntimeError("spectral centered series is not exact mean-centered")
    autocorrelations = _binary_circular_autocorrelation(appearance)
    score = _spectral_parent.spectral_ipr_from_circular_autocorrelation(autocorrelations)
    if not Fraction(0, 1) <= score <= Fraction(1, 1):
        raise RuntimeError("spectral IPR component must lie in [0,1]")
    return score


def spectral_ipr_300(history: HistoryInput, target_index: int, number: int) -> Fraction:
    """Return one causal exact 300-window spectral IPR component."""

    valid_history = validate_prior_history(history, target_index)
    return _spectral_component_from_window(valid_history[-WINDOW:], number)


spectral_component_300 = spectral_ipr_300
spectral_component_for_number = spectral_ipr_300


def calculate_spectral_components(
    history: HistoryInput, target_index: int
) -> Components:
    """Return ``SPECTRAL_IPR_300(n)`` for all legal numbers in number order."""

    valid_history = validate_prior_history(history, target_index)
    window_draws = valid_history[-WINDOW:]
    return tuple(
        _spectral_component_from_window(window_draws, number)
        for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1)
    )


spectral_components = calculate_spectral_components


def ml_target_probability_300(
    history: HistoryInput, target_index: int, number: int
) -> Fraction:
    """Return one causal exact 300-example online AR6 target probability."""

    _validate_number(number)
    valid_history = validate_prior_history(history, target_index)
    model = _ml_parent.train_number_horizon_model(valid_history, number, ML_HORIZON)
    probability = model.TARGET_PROBABILITY
    if not Fraction(0, 1) <= probability <= Fraction(1, 1):
        raise RuntimeError("ML target probability must lie in [0,1]")
    return probability


ml_component_300 = ml_target_probability_300
ml_component_for_number = ml_target_probability_300


def calculate_ml_components(history: HistoryInput, target_index: int) -> Components:
    """Return ``TARGET_PROBABILITY_300(n)`` for all legal numbers."""

    valid_history = validate_prior_history(history, target_index)
    return tuple(
        _ml_parent.train_number_horizon_model(valid_history, number, ML_HORIZON).TARGET_PROBABILITY
        for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1)
    )


ml_components = calculate_ml_components


def _exact_component_values(
    values: Sequence[object] | Mapping[int, object], name: str
) -> Components:
    if isinstance(values, Mapping):
        keys = tuple(values)
        if len(keys) != RANKED_POOL_CARDINALITY or set(keys) != set(range(1, 50)):
            raise ValueError(f"{name} mapping must contain exactly keys 1..49")
        raw_values = tuple(values[number] for number in range(1, 50))
    else:
        raw_values = tuple(values)
        if len(raw_values) != RANKED_POOL_CARDINALITY:
            raise ValueError(f"{name} must contain exactly 49 components")

    converted: list[Fraction] = []
    for index, value in enumerate(raw_values, start=1):
        if isinstance(value, Fraction):
            exact = value
        elif type(value) is int:
            exact = Fraction(value, 1)
        else:
            raise TypeError(f"{name}[{index}] must use exact Fraction or integer arithmetic")
        if not Fraction(0, 1) <= exact <= Fraction(1, 1):
            raise ValueError(f"{name}[{index}] must lie in [0,1]")
        converted.append(exact)
    return tuple(converted)


def rank_pairwise_scores(
    spectral_components: Sequence[object] | Mapping[int, object],
    ml_components: Sequence[object] | Mapping[int, object],
) -> PairwiseRanking:
    """Fuse and rank two exact component vectors without observed normalization."""

    spectral = _exact_component_values(spectral_components, "spectral_components")
    ml = _exact_component_values(ml_components, "ml_components")
    scores = tuple(
        SPECTRAL_WEIGHT * spectral[index] + ML_WEIGHT * ml[index]
        for index in range(RANKED_POOL_CARDINALITY)
    )
    ranked_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-scores[number - 1], number),
        )
    )
    positions = [0] * RANKED_POOL_CARDINALITY
    for position, number in enumerate(ranked_numbers, start=1):
        positions[number - 1] = position
    score_records = tuple(
        PairwiseNumberScore(
            NUMBER=number,
            SPECTRAL_COMPONENT=spectral[number - 1],
            ML_COMPONENT=ml[number - 1],
            PAIRWISE_SCORE=scores[number - 1],
            POSITION=positions[number - 1],
        )
        for number in ranked_numbers
    )
    ticket = cast(Ticket, tuple(sorted(ranked_numbers[:PICK_COUNT])))
    if len(ticket) != PICK_COUNT or len(set(ticket)) != PICK_COUNT:
        raise RuntimeError("pairwise native ticket must contain six unique numbers")
    return PairwiseRanking(
        SPECTRAL_COMPONENTS=spectral,
        ML_COMPONENTS=ml,
        PAIRWISE_SCORES=scores,
        RANKED_NUMBERS=ranked_numbers,
        POSITIONS=tuple(positions),
        SCORES=score_records,
        NATIVE_TICKET=ticket,
    )


fuse_pairwise_scores = rank_pairwise_scores


def calculate_pairwise_ranking(history: HistoryInput, target_index: int) -> PairwiseRanking:
    """Calculate the causal pairwise ranking from both frozen parents."""

    spectral = calculate_spectral_components(history, target_index)
    ml = calculate_ml_components(history, target_index)
    return rank_pairwise_scores(spectral, ml)


calculate_fused_number_ranking = calculate_pairwise_ranking


def produce_ticket(history: HistoryInput, target_index: int) -> Ticket:
    """Return the one sorted native ticket selected from ranked positions 1..6."""

    return calculate_pairwise_ranking(history, target_index).NATIVE_TICKET


def produce_candidate_portfolio(history: HistoryInput, target_index: int) -> TicketPortfolio:
    """Return exactly one native ticket for the frozen candidate."""

    return (produce_ticket(history, target_index),)


produce_candidate = produce_candidate_portfolio
produce_source_ticket_universe = produce_candidate_portfolio
build_source_ticket_universe = produce_candidate_portfolio


produce_bmsgv1_l2_pairwise_signal_fourier_ml_like_weighted_score_candidate_batch_r1 = (
    produce_candidate_portfolio
)


produce_biglotto_l2_pairwise_signal_fourier_ml_like_weighted_score_candidate_batch_r1 = (
    produce_bmsgv1_l2_pairwise_signal_fourier_ml_like_weighted_score_candidate_batch_r1
)
produce_biglotto_l2_pairwise_signal_fourier_ml_like_weighted_score_candidate = (
    produce_bmsgv1_l2_pairwise_signal_fourier_ml_like_weighted_score_candidate_batch_r1
)


def _json_ready(value: object) -> object:
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        converted: dict[str, object] = {}
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
    if not isinstance(record, Mapping):
        raise TypeError("semantic record must be a mapping")
    return json.dumps(
        _json_ready(cast(Mapping[object, object], record)),
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
    if record.get("SELECTED_GAP_ID") != SELECTED_GAP_ID:
        raise ValueError("semantic record does not identify the selected gap")
    if record.get("DESIGN_ID") != DESIGN_ID:
        raise ValueError("semantic record does not identify the frozen design")
    if record.get("DESIGN_SIGNATURE_SHA256") != DESIGN_SIGNATURE_SHA256:
        raise ValueError("semantic record does not identify the frozen design signature")
    return CANDIDATE_ID


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    return CandidateIdentity(
        CANDIDATE_ID=candidate_id_for_semantics(record),
        SIGNATURE_HASH=DESIGN_SIGNATURE_SHA256,
        CANONICAL_SEMANTIC_JSON=canonical_semantic_json(record),
    )


CANDIDATE_METADATA: Final[CandidateMetadata] = CandidateMetadata(
    CANDIDATE_ID=CANDIDATE_ID,
    SELECTED_GAP_ID=SELECTED_GAP_ID,
    DESIGN_ID=DESIGN_ID,
    DESIGN_SIGNATURE_SHA256=DESIGN_SIGNATURE_SHA256,
    FEATURE_1=FEATURE_1,
    FEATURE_2=FEATURE_2,
    WINDOW=WINDOW,
    COMPONENT_NORMALIZATION=COMPONENT_NORMALIZATION,
    SPECTRAL_WEIGHT=SPECTRAL_WEIGHT_TEXT,
    ML_WEIGHT=ML_WEIGHT_TEXT,
    IMPLEMENTATION_MODULE=IMPLEMENTATION_MODULE,
    IMPLEMENTATION_SYMBOL=IMPLEMENTATION_SYMBOL,
    NATIVE_TICKET_COUNT=NATIVE_TICKET_COUNT,
    MINIMUM_HISTORY=MINIMUM_HISTORY,
    DETERMINISM_CLASS=DETERMINISM_CLASS,
    SEMANTICS=CANDIDATE_SEMANTICS,
)
CANDIDATE_AUTHORITIES: Final[tuple[CandidateMetadata, ...]] = (CANDIDATE_METADATA,)
CANDIDATE_AUTHORITY: Final[Mapping[str, CandidateMetadata]] = MappingProxyType(
    {CANDIDATE_ID: CANDIDATE_METADATA}
)
CANDIDATE_IDS: Final[tuple[str, ...]] = (CANDIDATE_ID,)
CANDIDATE_SEMANTICS_BY_ID: Final[Mapping[str, Mapping[str, object]]] = MappingProxyType(
    {CANDIDATE_ID: CANDIDATE_SEMANTICS}
)
CANDIDATE_SEMANTIC_RECORDS = CANDIDATE_SEMANTICS_BY_ID
CANDIDATE_SIGNATURE_HASHES: Final[Mapping[str, str]] = MappingProxyType(
    {CANDIDATE_ID: DESIGN_SIGNATURE_SHA256}
)


__all__ = [
    "CANDIDATE_AUTHORITIES",
    "CANDIDATE_AUTHORITY",
    "CANDIDATE_ID",
    "CANDIDATE_IDS",
    "CANDIDATE_METADATA",
    "CANDIDATE_SEMANTICS",
    "CANDIDATE_SEMANTICS_BY_ID",
    "CANDIDATE_SEMANTIC_RECORDS",
    "CANDIDATE_SIGNATURE_HASHES",
    "CAUSAL_CUTOFF_RULE",
    "COMPONENT_NORMALIZATION",
    "DESIGN_ID",
    "DESIGN_SIGNATURE_SHA256",
    "DETERMINISM_CLASS",
    "DOMINANT_PERIOD_USED_FOR_PRIMARY_SCORE",
    "EXPECTED_IMPROVEMENT_CHANNEL",
    "FEATURE_1",
    "FEATURE_2",
    "FLOATING_FFT_USED_FOR_RANKING",
    "IMPLEMENTATION_MODULE",
    "IMPLEMENTATION_SYMBOL",
    "LAST_HIT_GAP_USED",
    "MINIMUM_HISTORY",
    "ML_COMPONENT_RULE",
    "ML_HORIZON",
    "ML_PARENT_COMMIT",
    "ML_PARENT_ID",
    "ML_PRESERVATION_RULES",
    "ML_WEIGHT",
    "NATIVE_TICKET_COUNT",
    "NUMBER_DOMAIN",
    "NUMBER_RANKING_RULE",
    "OUTPUT_SHAPE",
    "PAIRWISE_SCORE_RULE",
    "PARAMETER_SELECTION_RULE",
    "PICK_COUNT",
    "RANKED_POOL_CARDINALITY",
    "RANKED_POOL_DOMAIN",
    "RANKED_POOL_RULE",
    "RNG",
    "RNG_SEMANTICS",
    "SELECTED_GAP_ID",
    "SOURCE_UNIVERSE_CONTRACT",
    "SOURCE_UNIVERSE_ID",
    "SOURCE_UNIVERSE_VERSION",
    "SPECTRAL_COMPONENT_RULE",
    "SPECTRAL_FORMULA",
    "SPECTRAL_PARENT_COMMIT",
    "SPECTRAL_PARENT_ID",
    "SPECTRAL_PRESERVATION_RULES",
    "SPECTRAL_WEIGHT",
    "SPECTRAL_WINDOW",
    "TICKET_CONSTRUCTION_RULE",
    "TICKET_SELECTION_RULE",
    "WINDOW",
    "CandidateIdentity",
    "CandidateMetadata",
    "HistoryDraw",
    "HistoryInput",
    "InsufficientHistoryError",
    "PairwiseNumberScore",
    "PairwiseRanking",
    "Ticket",
    "TicketPortfolio",
    "calculate_fused_number_ranking",
    "calculate_ml_components",
    "calculate_pairwise_ranking",
    "calculate_spectral_components",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "fuse_pairwise_scores",
    "ml_component_300",
    "ml_component_for_number",
    "ml_components",
    "ml_target_probability_300",
    "produce_biglotto_l2_pairwise_signal_fourier_ml_like_weighted_score_candidate",
    "produce_biglotto_l2_pairwise_signal_fourier_ml_like_weighted_score_candidate_batch_r1",
    "produce_bmsgv1_l2_pairwise_signal_fourier_ml_like_weighted_score_candidate_batch_r1",
    "produce_candidate",
    "produce_candidate_portfolio",
    "produce_source_ticket_universe",
    "produce_ticket",
    "rank_pairwise_scores",
    "signature_hash_for_semantics",
    "spectral_component_300",
    "spectral_component_for_number",
    "spectral_components",
    "spectral_ipr_300",
    "validate_history",
    "validate_prior_history",
]
