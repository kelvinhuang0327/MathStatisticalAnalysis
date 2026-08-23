"""Causal BigLotto multiscale Bayesian changepoint BMA candidate batch R1.

This module freezes one history-only source-ticket universe:
B649_MULTISCALE_BAYES_CHANGEPOINT_BMA_RANKED_POOL_V1.

For every number and each fixed window (50, 300, 750), two preregistered
Bayesian Bernoulli models are compared:
M0: one stable occurrence probability over the full window.
M1: independent occurrence probabilities for the older half and recent half.

Using a fixed Beta(6, 43) prior derived from the official 6/49 combinatorial
lottery structure and equal prior model probabilities P(M0) = P(M1) = 1/2,
exact marginal evidence factors, posterior model probabilities, and posterior
model-averaged (BMA) predictive probabilities for the next draw are computed
using exact rational arithmetic.

The three independent per-window rankings are fused with equal rank aggregation.
The top 10 numbers generate exactly C(10, 6) = 210 ordered source tickets, which
are passed directly to the three frozen portfolio constructors at native
budgets 5, 10, and 20 to produce exactly 9 frozen hypotheses.

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
type RationalRanks = tuple[Fraction, ...]
type TicketPortfolio = tuple[Ticket, ...]

HYPOTHESIS_VERSION: Final[str] = "V1"
SOURCE_UNIVERSE_ID: Final[str] = (
    "B649_MULTISCALE_BAYES_CHANGEPOINT_BMA_RANKED_POOL_V1"
)
SOURCE_UNIVERSE_VERSION: Final[str] = "v1"
METHOD_FAMILY: Final[str] = "BAYESIAN_PROBABILISTIC"
LOTTERY_TYPE: Final[str] = "BIG_LOTTO"
PICK_COUNT: Final[int] = 6
NUMBER_DOMAIN: Final[tuple[int, int]] = (1, 49)
HISTORY_ORDER: Final[str] = "CHRONOLOGICAL_OLDEST_TO_NEWEST"
BAYES_WINDOWS: Final[tuple[int, int, int]] = (50, 300, 750)
WINDOWS: Final[tuple[int, int, int]] = BAYES_WINDOWS
SOURCE_WINDOWS: Final[tuple[int, int, int]] = BAYES_WINDOWS
MINIMUM_HISTORY: Final[int] = 750
TOP_NUMBER_COUNT: Final[int] = 10
SOURCE_CANDIDATE_TICKET_COUNT: Final[int] = 210
SOURCE_TICKET_ORDER: Final[str] = "LEXICOGRAPHIC_RANK_POSITION_COMBINATION_ORDER"

WINDOW_SPLIT_RULE: Final[str] = "FIXED_EQUAL_OLDER_RECENT_HALVES"
PRIOR_FAMILY: Final[str] = "BETA"
PRIOR_ALPHA: Final[int] = 6
PRIOR_BETA: Final[int] = 43
PRIOR_SOURCE: Final[str] = "OFFICIAL_SYMMETRIC_BIGLOTTO_MARGINAL_6_OVER_49"
PRIOR_MEAN: Final[Fraction] = Fraction(6, 49)
PRIOR_STRENGTH: Final[int] = 49

MODEL_M0: Final[str] = "STABLE_SINGLE_BERNOULLI_RATE_OVER_FULL_WINDOW"
MODEL_M1: Final[str] = "TWO_REGIME_INDEPENDENT_BERNOULLI_RATES_OLDER_VS_RECENT"
MODEL_PRIOR_RULE: Final[str] = "EXACT_EQUAL_ONE_HALF_EACH"
MODEL_PRIOR_M0: Final[Fraction] = Fraction(1, 2)
MODEL_PRIOR_M1: Final[Fraction] = Fraction(1, 2)

BETA_EVIDENCE_RULE: Final[str] = (
    "BETA_EVIDENCE(alpha,beta,k,N)=(alpha)_k*(beta)_(N-k)/(alpha+beta)_N;EXACT_RATIONAL"
)
M0_EVIDENCE_RULE: Final[str] = (
    "EVIDENCE_M0_W(n)=BETA_EVIDENCE(6,43,K_TOTAL_W(n),W)"
)
M1_EVIDENCE_RULE: Final[str] = (
    "EVIDENCE_M1_W(n)=BETA_EVIDENCE(6,43,K_OLD_W(n),HALF_W)*"
    "BETA_EVIDENCE(6,43,K_RECENT_W(n),HALF_W)"
)
POSTERIOR_MODEL_RULE: Final[str] = (
    "POSTERIOR_M1_W(n)=EVIDENCE_M1_W(n)/(EVIDENCE_M0_W(n)+EVIDENCE_M1_W(n));"
    "POSTERIOR_M0_W(n)=1-POSTERIOR_M1_W(n)"
)
M0_PREDICTIVE_RULE: Final[str] = "PREDICTIVE_M0_W(n)=(6+K_TOTAL_W(n))/(49+W)"
M1_PREDICTIVE_RULE: Final[str] = (
    "PREDICTIVE_M1_W(n)=(6+K_RECENT_W(n))/(49+HALF_W)"
)
BMA_PREDICTIVE_RULE: Final[str] = (
    "BMA_PREDICTIVE_W(n)=POSTERIOR_M0_W(n)*PREDICTIVE_M0_W(n)+"
    "POSTERIOR_M1_W(n)*PREDICTIVE_M1_W(n)"
)
GLOBAL_RENORMALIZATION_RULE: Final[str] = "NONE"

PER_WINDOW_RANKING_RULE: Final[str] = (
    "BMA_PREDICTIVE_DESCENDING_POSTERIOR_M1_DESCENDING_"
    "PREDICTIVE_M1_DESCENDING_NUMBER_ASCENDING"
)
WINDOW_NORMALIZATION_RULE: Final[str] = (
    "NORMALIZED=(49-POSITION)/48;EXACT_RATIONAL"
)
WINDOW_FUSION_RULE: Final[str] = (
    "EQUAL_RANK_AGGREGATION;MEAN=(NORMALIZED_50+NORMALIZED_300+"
    "NORMALIZED_750)/3;ROBUSTNESS_TIE_BREAK"
)
ROBUSTNESS_RULE: Final[str] = "SORTED_ASCENDING=(MINIMUM,MEDIAN,MAXIMUM)"
CAUSAL_CUTOFF_RULE: Final[str] = "STRICTLY_PRIOR_HISTORY_EXCLUSIVE_TARGET_INDEX"
PARAMETER_SELECTION_RULE: Final[str] = "FIXED_PREREGISTERED_NO_OUTCOME_TUNING"
DETERMINISM_CLASS: Final[str] = "PURE_DETERMINISTIC_NO_RNG"
RNG_SEMANTICS: Final[str] = "NONE"
OUTPUT_SHAPE: Final[str] = "PORTFOLIO"
EXPECTED_IMPROVEMENT_CHANNEL: Final[str] = (
    "BAYESIAN_STABLE_VS_RECENT_RATE_CHANGE_MODEL_AVERAGING"
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
_CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS: Final[Mapping[str, str]] = (
    MappingProxyType(
        {
            "B649_CANDIDATE_SET_LOW_OVERLAP_V1": "TICKET_PAIRWISE_DIVERSITY",
            "B649_CANDIDATE_SET_EXPOSURE_BALANCED_V1": (
                "NUMBER_EXPOSURE_DIVERSITY"
            ),
            "B649_CANDIDATE_SET_HYBRID_DIVERSITY_V1": (
                "PAIRWISE_AND_NUMBER_EXPOSURE_DIVERSITY"
            ),
        }
    )
)


class InsufficientHistoryError(ValueError):
    """Raised when fewer than the preregistered 750 prior draws are available."""


@dataclass(frozen=True, slots=True)
class SourceUniverseMetadata:
    """Immutable authority metadata for the Bayesian changepoint BMA source universe."""

    SOURCE_UNIVERSE_ID: str
    VERSION: str
    METHOD_FAMILY: str
    LOTTERY_TYPE: str
    PICK_COUNT: int
    NUMBER_DOMAIN: tuple[int, int]
    HISTORY_ORDER: str
    BAYES_WINDOWS: tuple[int, int, int]
    MINIMUM_HISTORY: int
    WINDOW_SPLIT_RULE: str
    PRIOR_FAMILY: str
    PRIOR_ALPHA: int
    PRIOR_BETA: int
    PRIOR_SOURCE: str
    MODEL_M0: str
    MODEL_M1: str
    MODEL_PRIOR_RULE: str
    BETA_EVIDENCE_RULE: str
    M0_EVIDENCE_RULE: str
    M1_EVIDENCE_RULE: str
    POSTERIOR_MODEL_RULE: str
    M0_PREDICTIVE_RULE: str
    M1_PREDICTIVE_RULE: str
    BMA_PREDICTIVE_RULE: str
    GLOBAL_RENORMALIZATION_RULE: str
    PER_WINDOW_RANKING_RULE: str
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


SOURCE_UNIVERSE_METADATA: Final[SourceUniverseMetadata] = (
    SourceUniverseMetadata(
        SOURCE_UNIVERSE_ID=SOURCE_UNIVERSE_ID,
        VERSION=SOURCE_UNIVERSE_VERSION,
        METHOD_FAMILY=METHOD_FAMILY,
        LOTTERY_TYPE=LOTTERY_TYPE,
        PICK_COUNT=PICK_COUNT,
        NUMBER_DOMAIN=NUMBER_DOMAIN,
        HISTORY_ORDER=HISTORY_ORDER,
        BAYES_WINDOWS=BAYES_WINDOWS,
        MINIMUM_HISTORY=MINIMUM_HISTORY,
        WINDOW_SPLIT_RULE=WINDOW_SPLIT_RULE,
        PRIOR_FAMILY=PRIOR_FAMILY,
        PRIOR_ALPHA=PRIOR_ALPHA,
        PRIOR_BETA=PRIOR_BETA,
        PRIOR_SOURCE=PRIOR_SOURCE,
        MODEL_M0=MODEL_M0,
        MODEL_M1=MODEL_M1,
        MODEL_PRIOR_RULE=MODEL_PRIOR_RULE,
        BETA_EVIDENCE_RULE=BETA_EVIDENCE_RULE,
        M0_EVIDENCE_RULE=M0_EVIDENCE_RULE,
        M1_EVIDENCE_RULE=M1_EVIDENCE_RULE,
        POSTERIOR_MODEL_RULE=POSTERIOR_MODEL_RULE,
        M0_PREDICTIVE_RULE=M0_PREDICTIVE_RULE,
        M1_PREDICTIVE_RULE=M1_PREDICTIVE_RULE,
        BMA_PREDICTIVE_RULE=BMA_PREDICTIVE_RULE,
        GLOBAL_RENORMALIZATION_RULE=GLOBAL_RENORMALIZATION_RULE,
        PER_WINDOW_RANKING_RULE=PER_WINDOW_RANKING_RULE,
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
        EXPECTED_IMPROVEMENT_CHANNEL=EXPECTED_IMPROVEMENT_CHANNEL,
    )
)

SOURCE_UNIVERSE_CONTRACT: Final[Mapping[str, object]] = MappingProxyType(
    {
        "BAYES_WINDOWS": BAYES_WINDOWS,
        "BETA_EVIDENCE_RULE": BETA_EVIDENCE_RULE,
        "BMA_PREDICTIVE_RULE": BMA_PREDICTIVE_RULE,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "GLOBAL_RENORMALIZATION_RULE": GLOBAL_RENORMALIZATION_RULE,
        "HISTORY_ORDER": HISTORY_ORDER,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "M0_EVIDENCE_RULE": M0_EVIDENCE_RULE,
        "M0_PREDICTIVE_RULE": M0_PREDICTIVE_RULE,
        "M1_EVIDENCE_RULE": M1_EVIDENCE_RULE,
        "M1_PREDICTIVE_RULE": M1_PREDICTIVE_RULE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "MODEL_M0": MODEL_M0,
        "MODEL_M1": MODEL_M1,
        "MODEL_PRIOR_RULE": MODEL_PRIOR_RULE,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PER_WINDOW_RANKING_RULE": PER_WINDOW_RANKING_RULE,
        "PICK_COUNT": PICK_COUNT,
        "POSTERIOR_MODEL_RULE": POSTERIOR_MODEL_RULE,
        "PRIOR_ALPHA": PRIOR_ALPHA,
        "PRIOR_BETA": PRIOR_BETA,
        "PRIOR_FAMILY": PRIOR_FAMILY,
        "PRIOR_SOURCE": PRIOR_SOURCE,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
        "WINDOWS": WINDOWS,
        "WINDOW_FUSION_RULE": WINDOW_FUSION_RULE,
        "WINDOW_NORMALIZATION_RULE": WINDOW_NORMALIZATION_RULE,
        "WINDOW_SPLIT_RULE": WINDOW_SPLIT_RULE,
    }
)


@dataclass(frozen=True, slots=True)
class WindowRanking:
    """Exact counts, evidence, posterior probabilities, and ranks for one window."""

    WINDOW: int
    WINDOW_DRAW_COUNT: int
    OLDER_DRAW_COUNT: int
    RECENT_DRAW_COUNT: int
    K_OLD_COUNTS: tuple[int, ...]
    K_RECENT_COUNTS: tuple[int, ...]
    K_TOTAL_COUNTS: tuple[int, ...]
    M0_EVIDENCE: RationalRanks
    M1_EVIDENCE: RationalRanks
    POSTERIOR_M0: RationalRanks
    POSTERIOR_M1: RationalRanks
    PREDICTIVE_M0: RationalRanks
    PREDICTIVE_M1: RationalRanks
    BMA_PREDICTIVE: RationalRanks
    ORDERED_NUMBERS: tuple[int, ...]
    POSITIONS: tuple[int, ...]
    NORMALIZED_RANKS: RationalRanks

    @property
    def SCORES(self) -> RationalRanks:
        """Compatibility alias for exact BMA predictive score vector."""

        return self.BMA_PREDICTIVE

    @property
    def DRAW_COUNT(self) -> int:
        """Return the W strictly prior draws used by this window."""

        return self.WINDOW_DRAW_COUNT

    def k_old(self, number: int) -> int:
        _validate_number(number)
        return self.K_OLD_COUNTS[number - 1]

    def k_recent(self, number: int) -> int:
        _validate_number(number)
        return self.K_RECENT_COUNTS[number - 1]

    def k_total(self, number: int) -> int:
        _validate_number(number)
        return self.K_TOTAL_COUNTS[number - 1]

    def m0_evidence(self, number: int) -> Fraction:
        _validate_number(number)
        return self.M0_EVIDENCE[number - 1]

    def m1_evidence(self, number: int) -> Fraction:
        _validate_number(number)
        return self.M1_EVIDENCE[number - 1]

    def posterior_m0(self, number: int) -> Fraction:
        _validate_number(number)
        return self.POSTERIOR_M0[number - 1]

    def posterior_m1(self, number: int) -> Fraction:
        _validate_number(number)
        return self.POSTERIOR_M1[number - 1]

    def predictive_m0(self, number: int) -> Fraction:
        _validate_number(number)
        return self.PREDICTIVE_M0[number - 1]

    def predictive_m1(self, number: int) -> Fraction:
        _validate_number(number)
        return self.PREDICTIVE_M1[number - 1]

    def bma_predictive(self, number: int) -> Fraction:
        _validate_number(number)
        return self.BMA_PREDICTIVE[number - 1]

    def score(self, number: int) -> Fraction:
        return self.bma_predictive(number)

    def position(self, number: int) -> int:
        _validate_number(number)
        return self.POSITIONS[number - 1]

    def normalized_rank(self, number: int) -> Fraction:
        _validate_number(number)
        return self.NORMALIZED_RANKS[number - 1]


@dataclass(frozen=True, slots=True)
class FusedNumberRanking:
    """Three-window fusion with exact rational rank means and robustness."""

    ORDERED_NUMBERS: tuple[int, ...]
    MEAN_RANKS: RationalRanks
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
    if (
        type(number) is not int
        or not NUMBER_DOMAIN[0] <= number <= NUMBER_DOMAIN[1]
    ):
        raise ValueError(
            f"number must be an integer in {NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}"
        )


def _validate_target_index(target_index: int) -> None:
    if type(target_index) is not int or target_index < 0:
        raise ValueError("target_index must be a non-negative integer")


def _read_history_prefix(
    history: HistoryInput, target_index: int
) -> tuple[object, ...]:
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
        raise ValueError(
            "history must be a finite chronological sequence of draws"
        ) from error


def _validate_draw(raw_draw: object, draw_index: int) -> HistoryDraw:
    try:
        values: tuple[object, ...] = tuple(cast(Iterable[object], raw_draw))
    except TypeError as error:
        raise ValueError(
            f"history[{draw_index}] must contain exactly six integers"
        ) from error

    if len(values) != PICK_COUNT:
        raise ValueError(
            f"history[{draw_index}] must contain exactly {PICK_COUNT} numbers"
        )

    numbers: list[int] = []
    for position, raw_number in enumerate(values):
        if type(raw_number) is not int:
            raise ValueError(
                f"history[{draw_index}][{position}] must be an integer"
            )
        if not NUMBER_DOMAIN[0] <= raw_number <= NUMBER_DOMAIN[1]:
            raise ValueError(
                f"history[{draw_index}][{position}] must be in "
                f"{NUMBER_DOMAIN[0]}..{NUMBER_DOMAIN[1]}"
            )
        numbers.append(raw_number)

    if len(set(numbers)) != PICK_COUNT:
        raise ValueError(
            f"history[{draw_index}] must contain six unique numbers"
        )
    return cast(HistoryDraw, tuple(numbers))


def validate_prior_history(
    history: HistoryInput, target_index: int
) -> tuple[HistoryDraw, ...]:
    """Return an immutable copy of only the strictly prior validated history."""

    raw_prefix = _read_history_prefix(history, target_index)
    if len(raw_prefix) < MINIMUM_HISTORY:
        raise InsufficientHistoryError(
            f"insufficient history: target_index provides {len(raw_prefix)} prior draws; "
            f"at least {MINIMUM_HISTORY} are required"
        )
    return tuple(
        _validate_draw(raw_draw, index)
        for index, raw_draw in enumerate(raw_prefix)
    )


def _validate_window(window: int) -> None:
    if type(window) is not int or window not in BAYES_WINDOWS:
        raise ValueError(f"window must be one of {BAYES_WINDOWS}")


def rising_factorial(x: int, m: int) -> int:
    """Compute the rising factorial (x)_m = x * (x+1) * ... * (x+m-1).

    If m == 0, returns 1.
    """

    if type(x) is not int or x <= 0:
        raise ValueError("x must be a positive integer")
    if type(m) is not int or m < 0:
        raise ValueError("m must be a non-negative integer")
    if m == 0:
        return 1
    result = 1
    for i in range(m):
        result *= x + i
    return result


def beta_evidence(alpha: int, beta: int, k: int, n: int) -> Fraction:
    """Compute exact beta marginal evidence factor using rational rising factorials.

    BETA_EVIDENCE(alpha, beta, k, N) = (alpha)_k * (beta)_(N-k) / (alpha+beta)_N
    """

    if type(alpha) is not int or alpha <= 0:
        raise ValueError("alpha must be a positive integer")
    if type(beta) is not int or beta <= 0:
        raise ValueError("beta must be a positive integer")
    if type(k) is not int or k < 0:
        raise ValueError("k must be a non-negative integer")
    if type(n) is not int or n < 0:
        raise ValueError("n must be a non-negative integer")
    if k > n:
        raise ValueError("k must not exceed n")

    num = rising_factorial(alpha, k) * rising_factorial(beta, n - k)
    den = rising_factorial(alpha + beta, n)
    return Fraction(num, den)


def calculate_occurrences(
    draws: Sequence[HistoryDraw],
) -> tuple[int, ...]:
    """Count occurrences of each number in 1..49 across the provided draws."""

    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    counts = [0] * domain_size
    for draw in draws:
        for number in draw:
            counts[number - 1] += 1
    return tuple(counts)


def calculate_half_window_occurrences(
    window_draws: Sequence[HistoryDraw],
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Calculate (k_old, k_recent, k_total) counts for each number in 1..49."""

    window_len = len(window_draws)
    half_len = window_len // 2
    older_draws = window_draws[:half_len]
    recent_draws = window_draws[half_len:]

    k_old = calculate_occurrences(older_draws)
    k_recent = calculate_occurrences(recent_draws)
    k_total = tuple(
        old + recent for old, recent in zip(k_old, k_recent, strict=True)
    )
    return k_old, k_recent, k_total


def calculate_m0_evidence(
    k_total: Sequence[int], window: int
) -> tuple[Fraction, ...]:
    """Calculate exact M0 marginal evidence for each number.

    EVIDENCE_M0_W(n) = BETA_EVIDENCE(6, 43, K_TOTAL_W(n), W)
    """

    _validate_window(window)
    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    if len(k_total) != domain_size:
        raise ValueError(f"k_total must contain exactly {domain_size} values")

    return tuple(
        beta_evidence(PRIOR_ALPHA, PRIOR_BETA, k, window) for k in k_total
    )


def calculate_m1_evidence(
    k_old: Sequence[int], k_recent: Sequence[int], window: int
) -> tuple[Fraction, ...]:
    """Calculate exact M1 marginal evidence for each number.

    EVIDENCE_M1_W(n) = BETA_EVIDENCE(6, 43, K_OLD_W(n), HALF_W) *
                       BETA_EVIDENCE(6, 43, K_RECENT_W(n), HALF_W)
    """

    _validate_window(window)
    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    if len(k_old) != domain_size or len(k_recent) != domain_size:
        raise ValueError(f"counts must contain exactly {domain_size} values")

    half_w = window // 2
    ev_old = [
        beta_evidence(PRIOR_ALPHA, PRIOR_BETA, k, half_w) for k in k_old
    ]
    ev_recent = [
        beta_evidence(PRIOR_ALPHA, PRIOR_BETA, k, half_w) for k in k_recent
    ]
    return tuple(
        o * r for o, r in zip(ev_old, ev_recent, strict=True)
    )


def calculate_posterior_model_probabilities(
    m0_evidence: Sequence[Fraction], m1_evidence: Sequence[Fraction]
) -> tuple[tuple[Fraction, ...], tuple[Fraction, ...]]:
    """Calculate exact posterior probabilities (P(M0), P(M1)) for each number.

    Under equal model priors:
    POSTERIOR_M1 = EVIDENCE_M1 / (EVIDENCE_M0 + EVIDENCE_M1)
    POSTERIOR_M0 = 1 - POSTERIOR_M1 = EVIDENCE_M0 / (EVIDENCE_M0 + EVIDENCE_M1)
    """

    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    if len(m0_evidence) != domain_size or len(m1_evidence) != domain_size:
        raise ValueError(f"evidence must contain exactly {domain_size} values")

    p_m0: list[Fraction] = []
    p_m1: list[Fraction] = []
    for ev0, ev1 in zip(m0_evidence, m1_evidence, strict=True):
        total_ev = ev0 + ev1
        post1 = ev1 / total_ev
        post0 = ev0 / total_ev
        p_m0.append(post0)
        p_m1.append(post1)

    return tuple(p_m0), tuple(p_m1)


def calculate_predictive_m0(
    k_total: Sequence[int], window: int
) -> tuple[Fraction, ...]:
    """Calculate exact M0 predictive occurrence probability.

    PREDICTIVE_M0_W(n) = (6 + K_TOTAL_W(n)) / (49 + W)
    """

    _validate_window(window)
    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    if len(k_total) != domain_size:
        raise ValueError(f"k_total must contain exactly {domain_size} values")

    den = PRIOR_ALPHA + PRIOR_BETA + window
    return tuple(Fraction(PRIOR_ALPHA + k, den) for k in k_total)


def calculate_predictive_m1(
    k_recent: Sequence[int], window: int
) -> tuple[Fraction, ...]:
    """Calculate exact M1 predictive occurrence probability assuming recent regime.

    PREDICTIVE_M1_W(n) = (6 + K_RECENT_W(n)) / (49 + HALF_W)
    """

    _validate_window(window)
    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    if len(k_recent) != domain_size:
        raise ValueError(f"k_recent must contain exactly {domain_size} values")

    half_w = window // 2
    den = PRIOR_ALPHA + PRIOR_BETA + half_w
    return tuple(Fraction(PRIOR_ALPHA + k, den) for k in k_recent)


def calculate_bma_predictive(
    posterior_m0: Sequence[Fraction],
    posterior_m1: Sequence[Fraction],
    pred_m0: Sequence[Fraction],
    pred_m1: Sequence[Fraction],
) -> RationalRanks:
    """Calculate exact posterior-model-averaged predictive occurrence probability.

    BMA_PREDICTIVE_W(n) = POSTERIOR_M0 * PREDICTIVE_M0 + POSTERIOR_M1 * PREDICTIVE_M1
    """

    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    if (
        len(posterior_m0) != domain_size
        or len(posterior_m1) != domain_size
        or len(pred_m0) != domain_size
        or len(pred_m1) != domain_size
    ):
        raise ValueError(
            f"all arguments must contain exactly {domain_size} values"
        )

    return tuple(
        p0 * m0 + p1 * m1
        for p0, p1, m0, m1 in zip(
            posterior_m0, posterior_m1, pred_m0, pred_m1, strict=True
        )
    )


def _rank_validated_window(
    prior_history: tuple[HistoryDraw, ...], window: int
) -> WindowRanking:
    _validate_window(window)
    if len(prior_history) < window:
        raise InsufficientHistoryError(
            f"window {window} requires at least {window} prior draws"
        )

    window_draws = prior_history[-window:]
    half_w = window // 2
    k_old, k_recent, k_total = calculate_half_window_occurrences(window_draws)

    m0_ev = calculate_m0_evidence(k_total, window)
    m1_ev = calculate_m1_evidence(k_old, k_recent, window)
    post_m0, post_m1 = calculate_posterior_model_probabilities(m0_ev, m1_ev)
    pred_m0 = calculate_predictive_m0(k_total, window)
    pred_m1 = calculate_predictive_m1(k_recent, window)
    bma_pred = calculate_bma_predictive(post_m0, post_m1, pred_m0, pred_m1)

    ordered_numbers = tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (
                -bma_pred[number - 1],
                -post_m1[number - 1],
                -pred_m1[number - 1],
                number,
            ),
        )
    )

    domain_size = NUMBER_DOMAIN[1] - NUMBER_DOMAIN[0] + 1
    positions = [0] * domain_size
    normalized_ranks: list[Fraction] = [Fraction(0, 1)] * domain_size
    for position, number in enumerate(ordered_numbers, start=1):
        positions[number - 1] = position
        normalized_ranks[number - 1] = Fraction(49 - position, 48)

    return WindowRanking(
        WINDOW=window,
        WINDOW_DRAW_COUNT=len(window_draws),
        OLDER_DRAW_COUNT=half_w,
        RECENT_DRAW_COUNT=half_w,
        K_OLD_COUNTS=k_old,
        K_RECENT_COUNTS=k_recent,
        K_TOTAL_COUNTS=k_total,
        M0_EVIDENCE=m0_ev,
        M1_EVIDENCE=m1_ev,
        POSTERIOR_M0=post_m0,
        POSTERIOR_M1=post_m1,
        PREDICTIVE_M0=pred_m0,
        PREDICTIVE_M1=pred_m1,
        BMA_PREDICTIVE=bma_pred,
        ORDERED_NUMBERS=ordered_numbers,
        POSITIONS=tuple(positions),
        NORMALIZED_RANKS=tuple(normalized_ranks),
    )


def rank_numbers_by_window(
    history: HistoryInput, target_index: int, window: int
) -> WindowRanking:
    """Rank numbers using one exact Bayesian changepoint BMA window."""

    return _rank_validated_window(
        validate_prior_history(history, target_index), window
    )


def calculate_bayes_window(
    history: HistoryInput, target_index: int, window: int
) -> WindowRanking:
    """Compatibility alias for rank_numbers_by_window."""

    return rank_numbers_by_window(history, target_index, window)


def calculate_bma_scores(
    history: HistoryInput, target_index: int, window: int
) -> RationalRanks:
    """Return the exact BMA predictive score vector for one window."""

    return rank_numbers_by_window(history, target_index, window).BMA_PREDICTIVE


def raw_full_window_frequency_order(
    history: HistoryInput, target_index: int, window: int
) -> tuple[int, ...]:
    """Return raw full-window occurrence count order for specificity fixtures."""

    prior_history = validate_prior_history(history, target_index)
    _validate_window(window)
    window_draws = prior_history[-window:]
    occurrences = calculate_occurrences(window_draws)
    return tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-occurrences[number - 1], number),
        )
    )


def raw_recent_half_frequency_order(
    history: HistoryInput, target_index: int, window: int
) -> tuple[int, ...]:
    """Return raw recent-half occurrence count order for specificity fixtures."""

    prior_history = validate_prior_history(history, target_index)
    _validate_window(window)
    window_draws = prior_history[-window:]
    _, k_recent, _ = calculate_half_window_occurrences(window_draws)
    return tuple(
        sorted(
            range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1),
            key=lambda number: (-k_recent[number - 1], number),
        )
    )


def calculate_window_rankings(
    history: HistoryInput, target_index: int
) -> tuple[WindowRanking, WindowRanking, WindowRanking]:
    """Calculate the exact 50/300/750 Bayesian changepoint BMA rankings."""

    prior_history = validate_prior_history(history, target_index)
    rankings = tuple(
        _rank_validated_window(prior_history, window) for window in BAYES_WINDOWS
    )
    return cast(tuple[WindowRanking, WindowRanking, WindowRanking], rankings)


calculate_bayes_rankings = calculate_window_rankings


def fuse_window_rankings(
    window_rankings: Sequence[WindowRanking],
) -> FusedNumberRanking:
    """Fuse three window rankings with equal exact rational rank aggregation."""

    if tuple(ranking.WINDOW for ranking in window_rankings) != BAYES_WINDOWS:
        raise ValueError(
            f"window_rankings must contain windows in order {BAYES_WINDOWS}"
        )

    mean_ranks: list[Fraction] = []
    robustness: list[tuple[Fraction, Fraction, Fraction]] = []
    for number in range(NUMBER_DOMAIN[0], NUMBER_DOMAIN[1] + 1):
        normalized = tuple(
            ranking.normalized_rank(number) for ranking in window_rankings
        )
        mean_ranks.append(sum(normalized, Fraction(0, 1)) / len(normalized))
        sorted_ranks = tuple(sorted(normalized))
        robustness.append(
            cast(tuple[Fraction, Fraction, Fraction], sorted_ranks)
        )

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
    """Calculate the final fused number ranking from strictly prior history."""

    return fuse_window_rankings(calculate_window_rankings(history, target_index))


def produce_b649_multiscale_bayes_changepoint_bma_ranked_pool_v1(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce the ordered 210-ticket Bayesian changepoint BMA source universe."""

    fused_ranking = calculate_fused_number_ranking(history, target_index)
    top_numbers = fused_ranking.TOP_NUMBERS
    if len(top_numbers) != TOP_NUMBER_COUNT:
        raise RuntimeError(
            "fused ranking did not produce the configured top-number pool"
        )

    tickets: list[Ticket] = []
    for rank_positions in combinations(range(TOP_NUMBER_COUNT), PICK_COUNT):
        ticket = cast(
            Ticket,
            tuple(sorted(top_numbers[position] for position in rank_positions)),
        )
        tickets.append(ticket)

    source_tickets = tuple(tickets)
    if len(source_tickets) != SOURCE_CANDIDATE_TICKET_COUNT:
        raise RuntimeError("source universe did not produce exactly 210 tickets")
    if len(set(source_tickets)) != len(source_tickets):
        raise RuntimeError("source universe produced duplicate tickets")
    return source_tickets


produce_source_ticket_universe = (
    produce_b649_multiscale_bayes_changepoint_bma_ranked_pool_v1
)
build_source_ticket_universe = (
    produce_b649_multiscale_bayes_changepoint_bma_ranked_pool_v1
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
    """Return canonical semantic JSON as text."""

    return canonicalize_semantic_record(record).decode("utf-8")


def signature_hash_for_semantics(record: Mapping[str, object]) -> str:
    """Return the SHA-256 hash of canonical semantic JSON."""

    return hashlib.sha256(canonicalize_semantic_record(record)).hexdigest()


def candidate_id_for_semantics(record: Mapping[str, object]) -> str:
    """Derive the frozen Bayesian candidate ID."""

    return f"BMSGV1_BY_{signature_hash_for_semantics(record)[:16]}"


@dataclass(frozen=True, slots=True)
class CandidateIdentity:
    """Deterministic identity material for one Bayesian changepoint BMA hypothesis."""

    CANDIDATE_ID: str
    SIGNATURE_HASH: str
    CANONICAL_SEMANTIC_JSON: str


def derive_candidate_identity(record: Mapping[str, object]) -> CandidateIdentity:
    """Derive candidate ID and full signature hash together."""

    canonical_json = canonical_semantic_json(record)
    signature_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return CandidateIdentity(
        CANDIDATE_ID=f"BMSGV1_BY_{signature_hash[:16]}",
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
        "produce_b649_multiscale_bayes_changepoint_bma_multiticket_"
        f"{_CONSTRUCTOR_SYMBOL_SLUGS[constructor_id]}_v1_k{ticket_count}"
    )


def _candidate_semantic_record(
    constructor_id: str, ticket_count: int
) -> dict[str, object]:
    constructor_metadata = _constructors.CONSTRUCTOR_METADATA[constructor_id]
    return {
        "BAYES_WINDOWS": BAYES_WINDOWS,
        "BETA_EVIDENCE_RULE": BETA_EVIDENCE_RULE,
        "BMA_PREDICTIVE_RULE": BMA_PREDICTIVE_RULE,
        "CAUSAL_CUTOFF_RULE": CAUSAL_CUTOFF_RULE,
        "CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNEL": (
            _CONSTRUCTOR_EXPECTED_IMPROVEMENT_CHANNELS[constructor_id]
        ),
        "CONSTRUCTOR_ID": constructor_id,
        "CONSTRUCTOR_VERSION": constructor_metadata.VERSION,
        "DETERMINISM_CLASS": DETERMINISM_CLASS,
        "EXPECTED_IMPROVEMENT_CHANNEL": EXPECTED_IMPROVEMENT_CHANNEL,
        "GLOBAL_RENORMALIZATION_RULE": GLOBAL_RENORMALIZATION_RULE,
        "HISTORY_ORDER": HISTORY_ORDER,
        "HYPOTHESIS_VERSION": HYPOTHESIS_VERSION,
        "LOTTERY_TYPE": LOTTERY_TYPE,
        "M0_EVIDENCE_RULE": M0_EVIDENCE_RULE,
        "M0_PREDICTIVE_RULE": M0_PREDICTIVE_RULE,
        "M1_EVIDENCE_RULE": M1_EVIDENCE_RULE,
        "M1_PREDICTIVE_RULE": M1_PREDICTIVE_RULE,
        "METHOD_FAMILY": METHOD_FAMILY,
        "MINIMUM_HISTORY": MINIMUM_HISTORY,
        "MODEL_M0": MODEL_M0,
        "MODEL_M1": MODEL_M1,
        "MODEL_PRIOR_RULE": MODEL_PRIOR_RULE,
        "NATIVE_TICKET_COUNT": ticket_count,
        "NUMBER_DOMAIN": NUMBER_DOMAIN,
        "OUTPUT_SHAPE": OUTPUT_SHAPE,
        "PARAMETER_SELECTION_RULE": PARAMETER_SELECTION_RULE,
        "PER_WINDOW_RANKING_RULE": PER_WINDOW_RANKING_RULE,
        "PICK_COUNT": PICK_COUNT,
        "POSTERIOR_MODEL_RULE": POSTERIOR_MODEL_RULE,
        "PRIOR_ALPHA": PRIOR_ALPHA,
        "PRIOR_BETA": PRIOR_BETA,
        "PRIOR_FAMILY": PRIOR_FAMILY,
        "PRIOR_SOURCE": PRIOR_SOURCE,
        "RNG_SEED": None,
        "RNG_SEMANTICS": RNG_SEMANTICS,
        "ROBUSTNESS_RULE": ROBUSTNESS_RULE,
        "SOURCE_CANDIDATE_TICKET_COUNT": SOURCE_CANDIDATE_TICKET_COUNT,
        "SOURCE_TICKET_ORDER": SOURCE_TICKET_ORDER,
        "SOURCE_UNIVERSE_ID": SOURCE_UNIVERSE_ID,
        "SOURCE_UNIVERSE_VERSION": SOURCE_UNIVERSE_VERSION,
        "SOURCE_WINDOWS": SOURCE_WINDOWS,
        "TICKET_COUNT": ticket_count,
        "TOP_NUMBER_COUNT": TOP_NUMBER_COUNT,
        "WINDOWS": WINDOWS,
        "WINDOW_FUSION_RULE": WINDOW_FUSION_RULE,
        "WINDOW_NORMALIZATION_RULE": WINDOW_NORMALIZATION_RULE,
        "WINDOW_SPLIT_RULE": WINDOW_SPLIT_RULE,
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
            semantic_record = _candidate_semantic_record(
                constructor_id, ticket_count
            )
            identity = derive_candidate_identity(semantic_record)
            if identity.CANDIDATE_ID in metadata_by_id:
                raise RuntimeError(
                    "candidate ID collision in frozen Bayesian changepoint hypothesis matrix"
                )
            semantic_proxy: Mapping[str, object] = MappingProxyType(
                semantic_record
            )
            metadata = CandidateMetadata(
                CANDIDATE_ID=identity.CANDIDATE_ID,
                SIGNATURE_HASH=identity.SIGNATURE_HASH,
                SEMANTICS=semantic_proxy,
                CONSTRUCTOR_ID=constructor_id,
                TICKET_COUNT=ticket_count,
                IMPLEMENTATION_SYMBOL=_implementation_symbol(
                    constructor_id, ticket_count
                ),
            )
            authorities.append(metadata)
            metadata_by_id[identity.CANDIDATE_ID] = metadata
            semantics_by_id[identity.CANDIDATE_ID] = semantic_proxy
            ids_by_pair[(constructor_id, ticket_count)] = identity.CANDIDATE_ID

    expected_count = len(CONSTRUCTOR_IDS) * len(TICKET_COUNTS)
    if len(authorities) != expected_count:
        raise RuntimeError("candidate authority matrix is not exactly 3 by 3")
    if len({metadata.SIGNATURE_HASH for metadata in authorities}) != len(
        authorities
    ):
        raise RuntimeError(
            "candidate signature collision in frozen Bayesian changepoint matrix"
        )
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
        return CANDIDATE_IDS_BY_CONSTRUCTOR_AND_TICKET_COUNT[
            (constructor_id, ticket_count)
        ]
    except KeyError as error:
        raise KeyError(
            f"unsupported constructor/budget pair: {constructor_id!r}, {ticket_count!r}"
        ) from error


def _metadata_for_candidate(candidate_id: str) -> CandidateMetadata:
    try:
        return CANDIDATE_METADATA[candidate_id]
    except KeyError as error:
        raise KeyError(f"unknown candidate_id: {candidate_id!r}") from error


def produce_biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate(
    candidate_id: str, history: HistoryInput, target_index: int
) -> TicketPortfolio:
    """Produce one frozen Bayesian changepoint portfolio from strictly prior history."""

    metadata = _metadata_for_candidate(candidate_id)
    source_tickets = produce_source_ticket_universe(history, target_index)
    constructor = _constructors.CONSTRUCTORS[metadata.CONSTRUCTOR_ID]
    return constructor(source_tickets, metadata.TICKET_COUNT)


produce_biglotto_bayes_changepoint_bma_multi_ticket_candidate = (
    produce_biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate
)
produce_biglotto_multi_ticket_candidate = (
    produce_biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate
)
produce_multi_ticket_candidate = (
    produce_biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate
)
produce_candidate_portfolio = (
    produce_biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate
)


def _produce_named_candidate(
    constructor_id: str,
    ticket_count: int,
    history: HistoryInput,
    target_index: int,
) -> TicketPortfolio:
    return produce_biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate(
        candidate_id_for(constructor_id, ticket_count), history, target_index
    )


def produce_b649_multiscale_bayes_changepoint_bma_multiticket_low_overlap_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[0], 5, history, target_index
    )


def produce_b649_multiscale_bayes_changepoint_bma_multiticket_low_overlap_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[0], 10, history, target_index
    )


def produce_b649_multiscale_bayes_changepoint_bma_multiticket_low_overlap_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[0], 20, history, target_index
    )


def produce_b649_multiscale_bayes_changepoint_bma_multiticket_exposure_balanced_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[1], 5, history, target_index
    )


def produce_b649_multiscale_bayes_changepoint_bma_multiticket_exposure_balanced_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[1], 10, history, target_index
    )


def produce_b649_multiscale_bayes_changepoint_bma_multiticket_exposure_balanced_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[1], 20, history, target_index
    )


def produce_b649_multiscale_bayes_changepoint_bma_multiticket_hybrid_diversity_v1_k5(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[2], 5, history, target_index
    )


def produce_b649_multiscale_bayes_changepoint_bma_multiticket_hybrid_diversity_v1_k10(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[2], 10, history, target_index
    )


def produce_b649_multiscale_bayes_changepoint_bma_multiticket_hybrid_diversity_v1_k20(
    history: HistoryInput, target_index: int
) -> TicketPortfolio:
    return _produce_named_candidate(
        CONSTRUCTOR_IDS[2], 20, history, target_index
    )


__all__ = [
    "BAYES_WINDOWS",
    "BETA_EVIDENCE_RULE",
    "BMA_PREDICTIVE_RULE",
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
    "GLOBAL_RENORMALIZATION_RULE",
    "HISTORY_ORDER",
    "HYPOTHESIS_VERSION",
    "LOTTERY_TYPE",
    "M0_EVIDENCE_RULE",
    "M0_PREDICTIVE_RULE",
    "M1_EVIDENCE_RULE",
    "M1_PREDICTIVE_RULE",
    "METHOD_FAMILY",
    "MINIMUM_HISTORY",
    "MODEL_M0",
    "MODEL_M1",
    "MODEL_PRIOR_M0",
    "MODEL_PRIOR_M1",
    "MODEL_PRIOR_RULE",
    "NUMBER_DOMAIN",
    "OUTPUT_SHAPE",
    "PARAMETER_SELECTION_RULE",
    "PER_WINDOW_RANKING_RULE",
    "PICK_COUNT",
    "POSTERIOR_MODEL_RULE",
    "PRIOR_ALPHA",
    "PRIOR_BETA",
    "PRIOR_FAMILY",
    "PRIOR_MEAN",
    "PRIOR_SOURCE",
    "PRIOR_STRENGTH",
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
    "WINDOW_SPLIT_RULE",
    "CandidateIdentity",
    "CandidateMetadata",
    "FusedNumberRanking",
    "InsufficientHistoryError",
    "SourceUniverseMetadata",
    "WindowRanking",
    "beta_evidence",
    "build_source_ticket_universe",
    "calculate_bayes_rankings",
    "calculate_bayes_window",
    "calculate_bma_predictive",
    "calculate_bma_scores",
    "calculate_fused_number_ranking",
    "calculate_half_window_occurrences",
    "calculate_m0_evidence",
    "calculate_m1_evidence",
    "calculate_occurrences",
    "calculate_posterior_model_probabilities",
    "calculate_predictive_m0",
    "calculate_predictive_m1",
    "calculate_window_rankings",
    "candidate_id_for",
    "candidate_id_for_semantics",
    "canonical_semantic_json",
    "canonicalize_semantic_record",
    "derive_candidate_identity",
    "fuse_window_rankings",
    "produce_b649_multiscale_bayes_changepoint_bma_multiticket_exposure_balanced_v1_k5",
    "produce_b649_multiscale_bayes_changepoint_bma_multiticket_exposure_balanced_v1_k10",
    "produce_b649_multiscale_bayes_changepoint_bma_multiticket_exposure_balanced_v1_k20",
    "produce_b649_multiscale_bayes_changepoint_bma_multiticket_hybrid_diversity_v1_k5",
    "produce_b649_multiscale_bayes_changepoint_bma_multiticket_hybrid_diversity_v1_k10",
    "produce_b649_multiscale_bayes_changepoint_bma_multiticket_hybrid_diversity_v1_k20",
    "produce_b649_multiscale_bayes_changepoint_bma_multiticket_low_overlap_v1_k5",
    "produce_b649_multiscale_bayes_changepoint_bma_multiticket_low_overlap_v1_k10",
    "produce_b649_multiscale_bayes_changepoint_bma_multiticket_low_overlap_v1_k20",
    "produce_b649_multiscale_bayes_changepoint_bma_ranked_pool_v1",
    "produce_biglotto_bayes_changepoint_bma_multi_ticket_candidate",
    "produce_biglotto_multi_ticket_candidate",
    "produce_biglotto_multiscale_bayes_changepoint_bma_multi_ticket_candidate",
    "produce_candidate_portfolio",
    "produce_multi_ticket_candidate",
    "produce_source_ticket_universe",
    "rank_numbers_by_window",
    "raw_full_window_frequency_order",
    "raw_recent_half_frequency_order",
    "rising_factorial",
    "signature_hash_for_semantics",
    "validate_prior_history",
]
