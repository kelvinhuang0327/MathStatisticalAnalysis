"""Discovery-only causal interactions over the R1 historical replay features.

The finite selector universe is declared before scoring. Each rule uses one
feature as its primary lexicographic key, a second feature only for primary
ties, and canonical strategy identity for the final tie. The corpus accepted
by :func:`run_interaction_discovery` ends at the R1 discovery boundary, so the
already-consumed R1 confirmation labels cannot enter selection or
classification.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from fractions import Fraction
from itertools import combinations, product
from typing import cast

from lottolab.evidence import canonical_json
from lottolab.research.base_method_evaluation import (
    BIG_LOTTO_MATCH_CONTRACT,
    single_ticket_tier_probability,
)

STUDY_ID = "historical-replay-meta-feature-interaction-discovery-r2"
RESULT_SCHEMA_ID = "lottolab.research.historical_replay_meta_feature_interaction_discovery"
RESULT_SCHEMA_VERSION = "1.0.0"
PREREGISTRATION_SCHEMA_ID = (
    "lottolab.research.historical_replay_meta_feature_interaction_discovery_preregistration"
)
PREREGISTRATION_SCHEMA_VERSION = "1.0.0"

PINNED_R1_RESULT_SHA256 = "383680a0d07f97702e22407f8a068034297ee64e45044688e7b40b8bbb314aea"
MINIMUM_FEATURE_HISTORY = 300
DISCOVERY_DRAW_COUNT = 750
R1_WARMUP_DRAW_COUNT = 448
R1_TOTAL_ASSIGNMENT_COUNT = 1_498
TEMPORAL_WINDOW_DRAW_COUNTS = (50, 300, 750)
TOP_DISCOVERY_CANDIDATE_COUNT = 10

SELECTION_UNIT = "CANONICAL_FIRST_TICKET_ONE_TICKET_EXPOSURE"
FINAL_TIE_BREAKER = "LEXICOGRAPHIC_STRATEGY_ID_ASC"
FEATURE_KNOWLEDGE_CUTOFF = "STRICTLY_BEFORE_TARGET_DRAW"
R1_TEMPORAL_SPLIT_METHOD = "FIXED_LAST_750_DISCOVERY_LAST_300_CONFIRMATION"
DISCOVERY_QUERY_BOUNDARY = "INCLUSIVE_R1_DISCOVERY_LAST_TARGET"

M2_TIER = BIG_LOTTO_MATCH_CONTRACT.hit_tiers[1]
SINGLE_TICKET_M2_RANDOM_RATE = single_ticket_tier_probability(
    BIG_LOTTO_MATCH_CONTRACT,
    M2_TIER,
)
SINGLE_TICKET_AVG_MATCH_RANDOM = Fraction(36, 49)


class InteractionDiscoveryError(ValueError):
    """The corpus, R1 authority, or frozen R2 design is malformed."""


class SelectionDirection(StrEnum):
    MAX = "MAX"
    MIN = "MIN"


class FinalClassification(StrEnum):
    DISCOVERY_ONLY_CANDIDATE_FROZEN = "DISCOVERY_ONLY_CANDIDATE_FROZEN"
    NO_ROBUST_DISCOVERY_CANDIDATE = "NO_ROBUST_DISCOVERY_CANDIDATE"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InteractionDiscoveryError(message)


def _require_text(value: object, name: str) -> str:
    _require(type(value) is str and bool(value) and value == value.strip(), f"{name} invalid")
    assert isinstance(value, str)
    return value


def _require_sha256(value: object, name: str) -> str:
    resolved = _require_text(value, name)
    _require(
        len(resolved) == 64
        and all(character in "0123456789abcdef" for character in resolved),
        f"{name} must be a lowercase SHA-256",
    )
    return resolved


def _require_integer(value: object, name: str) -> int:
    _require(type(value) is int, f"{name} must be an integer")
    assert isinstance(value, int)
    return value


def _require_mapping(value: object, name: str) -> Mapping[str, object]:
    _require(isinstance(value, Mapping), f"{name} must be an object")
    return cast("Mapping[str, object]", value)


def _require_sequence(value: object, name: str) -> Sequence[object]:
    _require(
        isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray),
        f"{name} must be an array",
    )
    return cast("Sequence[object]", value)


def _require_iso_date(value: str, name: str) -> None:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise InteractionDiscoveryError(f"{name} must be an ISO date") from exc
    _require(parsed.isoformat() == value, f"{name} must use YYYY-MM-DD")


def exact_fraction_dict(value: Fraction) -> dict[str, int]:
    """Return the repository exact-rational object shape."""

    return {"denominator": value.denominator, "numerator": value.numerator}


def exact_fraction_text(value: Fraction) -> str:
    """Return an exact rational without introducing binary float authority."""

    return f"{value.numerator}/{value.denominator}"


def _fraction_from_object(value: object, name: str) -> Fraction:
    mapping = _require_mapping(value, name)
    numerator = _require_integer(mapping.get("numerator"), f"{name}.numerator")
    denominator = _require_integer(mapping.get("denominator"), f"{name}.denominator")
    _require(denominator > 0, f"{name}.denominator must be positive")
    return Fraction(numerator, denominator)


@dataclass(frozen=True, slots=True, order=True)
class DrawIdentity:
    draw_date: str
    draw_number: int
    draw_sha256: str

    def __post_init__(self) -> None:
        _require_iso_date(self.draw_date, "draw_date")
        _require(type(self.draw_number) is int and self.draw_number > 0, "draw_number invalid")
        _require_sha256(self.draw_sha256, "draw_sha256")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "draw_date": self.draw_date,
            "draw_number": self.draw_number,
            "draw_sha256": self.draw_sha256,
        }


def _draw_identity_from_object(value: object, name: str) -> DrawIdentity:
    mapping = _require_mapping(value, name)
    return DrawIdentity(
        draw_date=_require_text(mapping.get("draw_date"), f"{name}.draw_date"),
        draw_number=_require_integer(mapping.get("draw_number"), f"{name}.draw_number"),
        draw_sha256=_require_sha256(mapping.get("draw_sha256"), f"{name}.draw_sha256"),
    )


@dataclass(frozen=True, slots=True)
class DiscoveryPartition:
    split_method: str
    total_assignment_count: int
    warmup_count: int
    discovery_count: int
    discovery_first_target: DrawIdentity
    discovery_last_target: DrawIdentity

    def __post_init__(self) -> None:
        _require_text(self.split_method, "split_method")
        _require(
            type(self.total_assignment_count) is int and self.total_assignment_count > 0,
            "total_assignment_count invalid",
        )
        _require(
            type(self.warmup_count) is int and self.warmup_count >= MINIMUM_FEATURE_HISTORY,
            "warmup_count cannot satisfy feature history",
        )
        _require(
            type(self.discovery_count) is int and self.discovery_count > 0,
            "discovery_count invalid",
        )
        _require(
            self.discovery_first_target < self.discovery_last_target,
            "discovery target bounds invalid",
        )

    @property
    def source_draw_count(self) -> int:
        return self.warmup_count + self.discovery_count

    def canonical_dict(self) -> dict[str, object]:
        return {
            "confirmation_observation_count_loaded": 0,
            "discovery_count": self.discovery_count,
            "discovery_first_target": self.discovery_first_target.canonical_dict(),
            "discovery_last_target": self.discovery_last_target.canonical_dict(),
            "query_boundary": DISCOVERY_QUERY_BOUNDARY,
            "source_draw_count": self.source_draw_count,
            "split_method": self.split_method,
            "total_assignment_count_in_r1": self.total_assignment_count,
            "warmup_count": self.warmup_count,
        }


R1_DISCOVERY_PARTITION = DiscoveryPartition(
    split_method=R1_TEMPORAL_SPLIT_METHOD,
    total_assignment_count=R1_TOTAL_ASSIGNMENT_COUNT,
    warmup_count=R1_WARMUP_DRAW_COUNT,
    discovery_count=DISCOVERY_DRAW_COUNT,
    discovery_first_target=DrawIdentity(
        draw_date="2017-03-10",
        draw_number=106000024,
        draw_sha256="b7139bb186236c8f8f6c52e23c78605b87cde8354cde5268199e60463532d5a4",
    ),
    discovery_last_target=DrawIdentity(
        draw_date="2023-11-21",
        draw_number=112000105,
        draw_sha256="d98ff24f506c29f7dce26d4f2581acd2cc63534f43c319027bebfe0ca1371bfa",
    ),
)


@dataclass(frozen=True, slots=True)
class TicketPrediction:
    native_position: int
    main_numbers: tuple[int, ...]
    ticket_sha256: str

    def __post_init__(self) -> None:
        _require(
            type(self.native_position) is int and self.native_position >= 1,
            "native_position invalid",
        )
        _require(
            len(self.main_numbers) == 6
            and len(set(self.main_numbers)) == 6
            and tuple(sorted(self.main_numbers)) == self.main_numbers
            and all(type(number) is int and 1 <= number <= 49 for number in self.main_numbers),
            "main_numbers must be six sorted unique BIG_LOTTO numbers",
        )
        _require_sha256(self.ticket_sha256, "ticket_sha256")


@dataclass(frozen=True, slots=True)
class StrategyPrediction:
    strategy_id: str
    strategy_version: str
    tickets: tuple[TicketPrediction, ...]

    def __post_init__(self) -> None:
        _require_text(self.strategy_id, "strategy_id")
        _require_text(self.strategy_version, "strategy_version")
        _require(bool(self.tickets), "strategy prediction requires tickets")
        _require(
            tuple(ticket.native_position for ticket in self.tickets)
            == tuple(range(1, len(self.tickets) + 1)),
            "ticket positions must be contiguous from one",
        )

    @property
    def first_ticket(self) -> TicketPrediction:
        return self.tickets[0]


@dataclass(frozen=True, slots=True)
class StrategyTargetObservation:
    prediction: StrategyPrediction
    first_ticket_main_hit_count: int

    def __post_init__(self) -> None:
        _require(
            type(self.first_ticket_main_hit_count) is int
            and 0 <= self.first_ticket_main_hit_count <= 6,
            "first_ticket_main_hit_count invalid",
        )


@dataclass(frozen=True, slots=True)
class CorpusDraw:
    target: DrawIdentity
    cutoff: DrawIdentity
    winning_main_numbers: tuple[int, ...]
    strategies: tuple[StrategyTargetObservation, ...]

    def __post_init__(self) -> None:
        _require(self.cutoff < self.target, "cutoff must precede target")
        _require(
            len(self.winning_main_numbers) == 6
            and len(set(self.winning_main_numbers)) == 6
            and tuple(sorted(self.winning_main_numbers)) == self.winning_main_numbers,
            "winning_main_numbers invalid",
        )
        strategy_ids = tuple(item.prediction.strategy_id for item in self.strategies)
        _require(strategy_ids == tuple(sorted(strategy_ids)), "strategies must be sorted")
        _require(len(strategy_ids) == len(set(strategy_ids)), "duplicate strategy on target")


@dataclass(frozen=True, slots=True)
class RunInventory:
    run_id: str
    run_kind: str
    latest_status: str
    strategy_count: int
    target_row_count: int
    distinct_target_count: int

    def canonical_dict(self) -> dict[str, object]:
        return {
            "distinct_target_count": self.distinct_target_count,
            "latest_status": self.latest_status,
            "run_id": self.run_id,
            "run_kind": self.run_kind,
            "strategy_count": self.strategy_count,
            "target_row_count": self.target_row_count,
        }


@dataclass(frozen=True, slots=True)
class CorpusProfile:
    bounded_target_row_count: int
    bounded_ticket_row_count: int
    bounded_result_row_count: int
    common_draw_count: int
    rows_excluded_outside_common_intersection: int
    duplicate_native_ticket_position_count: int
    result_version_extra_count: int
    required_null_count: int
    invalid_json_count: int
    recomputed_hit_mismatch_count: int
    causal_date_violation_count: int
    run_inventory: tuple[RunInventory, ...]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "bounded_result_row_count": self.bounded_result_row_count,
            "bounded_target_row_count": self.bounded_target_row_count,
            "bounded_ticket_row_count": self.bounded_ticket_row_count,
            "causal_date_violation_count": self.causal_date_violation_count,
            "common_draw_count": self.common_draw_count,
            "duplicate_native_ticket_position_count": self.duplicate_native_ticket_position_count,
            "invalid_json_count": self.invalid_json_count,
            "recomputed_hit_mismatch_count": self.recomputed_hit_mismatch_count,
            "required_null_count": self.required_null_count,
            "result_version_extra_count": self.result_version_extra_count,
            "rows_excluded_outside_common_intersection": (
                self.rows_excluded_outside_common_intersection
            ),
            "run_inventory": [item.canonical_dict() for item in self.run_inventory],
        }


@dataclass(frozen=True, slots=True)
class HistoricalReplayDiscoveryCorpus:
    source_run_id: str
    source_run_kind: str
    source_dataset_identity: str
    source_dataset_sha256: str
    source_rule_contract_id: str
    latest_run_status: str
    strategies: tuple[str, ...]
    draws: tuple[CorpusDraw, ...]
    profile: CorpusProfile

    def __post_init__(self) -> None:
        for name in (
            "source_run_id",
            "source_run_kind",
            "source_dataset_identity",
            "source_dataset_sha256",
            "source_rule_contract_id",
            "latest_run_status",
        ):
            _require_text(getattr(self, name), name)
        _require(self.source_run_kind == "REFERENCE_BASELINE", "source must be reference")
        _require(self.latest_run_status == "COMPLETED", "source run must be completed")
        _require(self.strategies == tuple(sorted(self.strategies)), "strategy IDs not sorted")
        _require(len(self.strategies) >= 2, "at least two strategies are required")
        _require(len(self.draws) > MINIMUM_FEATURE_HISTORY, "insufficient causal history")
        _require(
            all(
                left.target < right.target
                for left, right in zip(self.draws, self.draws[1:], strict=False)
            ),
            "corpus draws must be strictly chronological",
        )
        for draw in self.draws:
            ids = tuple(item.prediction.strategy_id for item in draw.strategies)
            _require(ids == self.strategies, "common draw strategy set changed")


@dataclass(frozen=True, slots=True, order=True)
class FeatureDefinition:
    feature_id: str
    family: str
    exact_definition: str

    def canonical_dict(self) -> dict[str, str]:
        return {
            "exact_definition": self.exact_definition,
            "family": self.family,
            "feature_id": self.feature_id,
        }


FEATURE_DEFINITIONS: tuple[FeatureDefinition, ...] = (
    FeatureDefinition(
        "cross_strategy_jaccard_mean",
        "strategy_agreement",
        "mean Jaccard overlap of the current strategy first ticket "
        "with every other current first ticket",
    ),
    FeatureDefinition(
        "m2_momentum_w010_prev010",
        "ranking_momentum",
        "prior 10-draw first-ticket M2+ rate minus the immediately preceding 10-draw rate",
    ),
    FeatureDefinition(
        "m2_rank_improvement_w010_w050",
        "ranking_momentum",
        "competition rank on prior-50 M2+ rate minus competition rank on prior-10 M2+ rate",
    ),
    FeatureDefinition(
        "m2_stability_gap_w010_w050",
        "performance_stability",
        "absolute difference between prior-10 and prior-50 first-ticket M2+ rates",
    ),
    FeatureDefinition(
        "m2_stability_gap_w050_w300",
        "performance_stability",
        "absolute difference between prior-50 and prior-300 first-ticket M2+ rates",
    ),
    FeatureDefinition(
        "portfolio_internal_jaccard_mean",
        "portfolio_overlap_coverage",
        "mean pairwise Jaccard overlap among current native portfolio tickets; zero for one ticket",
    ),
    FeatureDefinition(
        "portfolio_ticket_count",
        "strategy_diversity",
        "current native portfolio ticket count used as a pre-draw strategy-shape feature only",
    ),
    FeatureDefinition(
        "portfolio_unique_coverage_ratio",
        "portfolio_overlap_coverage",
        "current unique portfolio-number count divided by six times native ticket count",
    ),
    FeatureDefinition(
        "prediction_frequency_shift_w010_w050",
        "number_frequency_regime",
        "current first-ticket number frequency over prior 10 draws "
        "minus its frequency over prior 50 draws",
    ),
    FeatureDefinition(
        "prediction_number_frequency_w050",
        "number_frequency_recency",
        "mean occurrence rate of current first-ticket numbers in the prior 50 winning draws",
    ),
    FeatureDefinition(
        "prediction_number_omission_mean",
        "number_frequency_recency",
        "mean strictly-prior draw omission length of current first-ticket numbers",
    ),
    FeatureDefinition(
        "prediction_pair_cooccurrence_w300",
        "cooccurrence_state",
        "mean co-occurrence rate of current first-ticket pairs in the prior 300 winning draws",
    ),
    FeatureDefinition(
        "recent_avg_match_w010",
        "recent_strategy_performance",
        "mean first-ticket main-hit count over the prior 10 targets",
    ),
    FeatureDefinition(
        "recent_avg_match_w050",
        "recent_strategy_performance",
        "mean first-ticket main-hit count over the prior 50 targets",
    ),
    FeatureDefinition(
        "recent_avg_match_w300",
        "recent_strategy_performance",
        "mean first-ticket main-hit count over the prior 300 targets",
    ),
    FeatureDefinition(
        "recent_m2_rate_w010",
        "recent_strategy_hit_rate",
        "first-ticket M2+ success rate over the prior 10 targets",
    ),
    FeatureDefinition(
        "recent_m2_rate_w050",
        "recent_strategy_hit_rate",
        "first-ticket M2+ success rate over the prior 50 targets",
    ),
    FeatureDefinition(
        "recent_m2_rate_w300",
        "recent_strategy_hit_rate",
        "first-ticket M2+ success rate over the prior 300 targets",
    ),
)

FEATURE_COUNT = len(FEATURE_DEFINITIONS)
_FEATURE_IDS = tuple(item.feature_id for item in FEATURE_DEFINITIONS)
_require(FEATURE_COUNT == 18, "R1 feature universe must contain exactly 18 features")
_require(tuple(sorted(_FEATURE_IDS)) == _FEATURE_IDS, "feature definitions must be sorted")
_require(len(_FEATURE_IDS) == len(set(_FEATURE_IDS)), "duplicate feature definition")


@dataclass(frozen=True, slots=True)
class InteractionRule:
    candidate_id: str
    primary_feature: FeatureDefinition
    primary_direction: SelectionDirection
    secondary_feature: FeatureDefinition
    secondary_direction: SelectionDirection

    @property
    def exact_rule(self) -> str:
        return (
            f"{self.primary_feature.feature_id} {self.primary_direction.value} primary; "
            f"{self.secondary_feature.feature_id} {self.secondary_direction.value} "
            f"resolves equal primary values; final ties use {FINAL_TIE_BREAKER}; "
            f"evaluate {SELECTION_UNIT}"
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "exact_rule": self.exact_rule,
            "final_tie_breaker": FINAL_TIE_BREAKER,
            "primary_direction": self.primary_direction.value,
            "primary_feature": self.primary_feature.canonical_dict(),
            "secondary_direction": self.secondary_direction.value,
            "secondary_feature": self.secondary_feature.canonical_dict(),
            "selection_unit": SELECTION_UNIT,
        }


def _build_interaction_rules() -> tuple[InteractionRule, ...]:
    directions = (SelectionDirection.MAX, SelectionDirection.MIN)
    rules: list[InteractionRule] = []
    for primary_feature, secondary_feature in combinations(FEATURE_DEFINITIONS, 2):
        for primary_direction, secondary_direction in product(directions, repeat=2):
            candidate_id = (
                "hrmfi_r2__"
                f"{primary_feature.feature_id}__{primary_direction.value.casefold()}__"
                f"{secondary_feature.feature_id}__{secondary_direction.value.casefold()}"
            )
            rules.append(
                InteractionRule(
                    candidate_id=candidate_id,
                    primary_feature=primary_feature,
                    primary_direction=primary_direction,
                    secondary_feature=secondary_feature,
                    secondary_direction=secondary_direction,
                )
            )
    return tuple(rules)


INTERACTION_RULES = _build_interaction_rules()
INTERACTION_CANDIDATE_COUNT = len(INTERACTION_RULES)
_require(
    INTERACTION_CANDIDATE_COUNT == 612,
    "interaction universe must contain C(18,2) * 4 = 612 rules",
)
_require(
    len({rule.candidate_id for rule in INTERACTION_RULES}) == INTERACTION_CANDIDATE_COUNT,
    "duplicate interaction candidate identity",
)


def candidate_universe_sha256() -> str:
    """Hash the complete ordered selector universe."""

    return canonical_json.sha256_hex(
        canonical_json.canonical_bytes([rule.canonical_dict() for rule in INTERACTION_RULES])
    )


@dataclass(frozen=True, slots=True)
class PriorOutcome:
    main_hit_count: int

    @property
    def m2_success(self) -> int:
        return int(self.main_hit_count >= 2)


@dataclass(frozen=True, slots=True)
class DrawFeatureFrame:
    draw: CorpusDraw
    feature_values: Mapping[str, Mapping[str, Fraction]]


def _mean(values: Sequence[int | Fraction]) -> Fraction:
    _require(bool(values), "mean requires observations")
    return sum((Fraction(value) for value in values), Fraction()) / len(values)


def _jaccard(left: frozenset[int], right: frozenset[int]) -> Fraction:
    union = left | right
    _require(bool(union), "Jaccard union is empty")
    return Fraction(len(left & right), len(union))


def _number_frequency(
    numbers: tuple[int, ...],
    prior_draws: Sequence[frozenset[int]],
    window: int,
) -> Fraction:
    selected = prior_draws[-window:]
    _require(len(selected) == window, "number-frequency history is incomplete")
    return Fraction(
        sum(int(number in winning) for winning in selected for number in numbers),
        len(numbers) * window,
    )


def _omission_mean(numbers: tuple[int, ...], prior_draws: Sequence[frozenset[int]]) -> Fraction:
    omissions: list[int] = []
    for number in numbers:
        omission = len(prior_draws) + 1
        for index, winning in enumerate(reversed(prior_draws), start=1):
            if number in winning:
                omission = index
                break
        omissions.append(omission)
    return _mean(omissions)


def _pair_cooccurrence(
    numbers: tuple[int, ...],
    prior_draws: Sequence[frozenset[int]],
    window: int,
) -> Fraction:
    selected = prior_draws[-window:]
    _require(len(selected) == window, "co-occurrence history is incomplete")
    pairs = tuple(combinations(numbers, 2))
    return Fraction(
        sum(
            int(left in winning and right in winning)
            for winning in selected
            for left, right in pairs
        ),
        len(pairs) * window,
    )


def _competition_rank(values: Mapping[str, Fraction], strategy_id: str) -> int:
    value = values[strategy_id]
    return 1 + sum(int(other > value) for other in values.values())


def _performance_features(history: Sequence[PriorOutcome]) -> dict[str, Fraction]:
    _require(len(history) >= MINIMUM_FEATURE_HISTORY, "strategy history is incomplete")

    def m2_rate(window: int, *, offset: int = 0) -> Fraction:
        end = len(history) - offset
        selected = history[end - window : end]
        _require(len(selected) == window, "M2 history window is incomplete")
        return Fraction(sum(item.m2_success for item in selected), window)

    def avg_match(window: int) -> Fraction:
        selected = history[-window:]
        _require(len(selected) == window, "average-match history window is incomplete")
        return Fraction(sum(item.main_hit_count for item in selected), window)

    m2_10 = m2_rate(10)
    m2_50 = m2_rate(50)
    m2_300 = m2_rate(300)
    return {
        "m2_momentum_w010_prev010": m2_10 - m2_rate(10, offset=10),
        "m2_stability_gap_w010_w050": abs(m2_10 - m2_50),
        "m2_stability_gap_w050_w300": abs(m2_50 - m2_300),
        "recent_avg_match_w010": avg_match(10),
        "recent_avg_match_w050": avg_match(50),
        "recent_avg_match_w300": avg_match(300),
        "recent_m2_rate_w010": m2_10,
        "recent_m2_rate_w050": m2_50,
        "recent_m2_rate_w300": m2_300,
    }


def _prediction_features(
    prediction: StrategyPrediction,
    all_predictions: Mapping[str, StrategyPrediction],
    prior_draws: Sequence[frozenset[int]],
) -> dict[str, Fraction]:
    first_numbers = prediction.first_ticket.main_numbers
    first_set = frozenset(first_numbers)
    other_sets = tuple(
        frozenset(item.first_ticket.main_numbers)
        for strategy_id, item in all_predictions.items()
        if strategy_id != prediction.strategy_id
    )
    portfolio_sets = tuple(frozenset(ticket.main_numbers) for ticket in prediction.tickets)
    internal_pairs = tuple(combinations(portfolio_sets, 2))
    portfolio_union = frozenset(
        number for ticket_numbers in portfolio_sets for number in ticket_numbers
    )
    internal_overlap = (
        _mean(tuple(_jaccard(left, right) for left, right in internal_pairs))
        if internal_pairs
        else Fraction()
    )
    return {
        "cross_strategy_jaccard_mean": _mean(
            tuple(_jaccard(first_set, other) for other in other_sets)
        ),
        "portfolio_internal_jaccard_mean": internal_overlap,
        "portfolio_ticket_count": Fraction(len(prediction.tickets)),
        "portfolio_unique_coverage_ratio": Fraction(
            len(portfolio_union), 6 * len(prediction.tickets)
        ),
        "prediction_frequency_shift_w010_w050": (
            _number_frequency(first_numbers, prior_draws, 10)
            - _number_frequency(first_numbers, prior_draws, 50)
        ),
        "prediction_number_frequency_w050": _number_frequency(first_numbers, prior_draws, 50),
        "prediction_number_omission_mean": _omission_mean(first_numbers, prior_draws),
        "prediction_pair_cooccurrence_w300": _pair_cooccurrence(first_numbers, prior_draws, 300),
    }


def build_feature_frames(
    corpus: HistoricalReplayDiscoveryCorpus,
) -> tuple[DrawFeatureFrame, ...]:
    """Build causal frames, appending each target outcome only after its frame."""

    prior_outcomes: dict[str, list[PriorOutcome]] = {
        strategy_id: [] for strategy_id in corpus.strategies
    }
    prior_draws: list[frozenset[int]] = []
    frames: list[DrawFeatureFrame] = []

    for chronological_index, draw in enumerate(corpus.draws):
        predictions = {item.prediction.strategy_id: item.prediction for item in draw.strategies}
        if chronological_index >= MINIMUM_FEATURE_HISTORY:
            values: dict[str, dict[str, Fraction]] = {}
            for strategy_id in corpus.strategies:
                combined = _performance_features(prior_outcomes[strategy_id])
                combined.update(
                    _prediction_features(
                        predictions[strategy_id],
                        predictions,
                        prior_draws,
                    )
                )
                values[strategy_id] = combined

            short_rates = {
                strategy_id: values[strategy_id]["recent_m2_rate_w010"]
                for strategy_id in corpus.strategies
            }
            medium_rates = {
                strategy_id: values[strategy_id]["recent_m2_rate_w050"]
                for strategy_id in corpus.strategies
            }
            for strategy_id in corpus.strategies:
                values[strategy_id]["m2_rank_improvement_w010_w050"] = Fraction(
                    _competition_rank(medium_rates, strategy_id)
                    - _competition_rank(short_rates, strategy_id)
                )
                _require(
                    set(values[strategy_id]) == set(_FEATURE_IDS),
                    "computed feature universe drifted from frozen R1 features",
                )
            frames.append(DrawFeatureFrame(draw=draw, feature_values=values))

        for item in draw.strategies:
            prior_outcomes[item.prediction.strategy_id].append(
                PriorOutcome(item.first_ticket_main_hit_count)
            )
        prior_draws.append(frozenset(draw.winning_main_numbers))

    return tuple(frames)


def _is_better(candidate: Fraction, selected: Fraction, direction: SelectionDirection) -> bool:
    if direction is SelectionDirection.MAX:
        return candidate > selected
    return candidate < selected


def select_strategy(frame: DrawFeatureFrame, rule: InteractionRule) -> str:
    """Apply primary, secondary, then strategy-ID lexicographic selection."""

    ordered_ids = tuple(sorted(frame.feature_values))
    _require(bool(ordered_ids), "feature frame has no strategies")
    selected = ordered_ids[0]
    for strategy_id in ordered_ids[1:]:
        selected_values = frame.feature_values[selected]
        candidate_values = frame.feature_values[strategy_id]
        primary_selected = selected_values[rule.primary_feature.feature_id]
        primary_candidate = candidate_values[rule.primary_feature.feature_id]
        if _is_better(primary_candidate, primary_selected, rule.primary_direction):
            selected = strategy_id
            continue
        if primary_candidate != primary_selected:
            continue
        secondary_selected = selected_values[rule.secondary_feature.feature_id]
        secondary_candidate = candidate_values[rule.secondary_feature.feature_id]
        if _is_better(secondary_candidate, secondary_selected, rule.secondary_direction):
            selected = strategy_id
    return selected


@dataclass(frozen=True, slots=True)
class SelectedDraw:
    target: DrawIdentity
    selected_strategy_id: str
    selected_main_hit_count: int
    pool_m2_success_count: int
    pool_main_hit_sum: int
    strategy_count: int

    @property
    def selected_m2_success(self) -> int:
        return int(self.selected_main_hit_count >= 2)


def _selected_series(
    frames: Sequence[DrawFeatureFrame], rule: InteractionRule
) -> tuple[SelectedDraw, ...]:
    selected: list[SelectedDraw] = []
    for frame in frames:
        strategy_id = select_strategy(frame, rule)
        outcomes = {
            item.prediction.strategy_id: item.first_ticket_main_hit_count
            for item in frame.draw.strategies
        }
        selected.append(
            SelectedDraw(
                target=frame.draw.target,
                selected_strategy_id=strategy_id,
                selected_main_hit_count=outcomes[strategy_id],
                pool_m2_success_count=sum(int(value >= 2) for value in outcomes.values()),
                pool_main_hit_sum=sum(outcomes.values()),
                strategy_count=len(outcomes),
            )
        )
    return tuple(selected)


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    support_count: int
    selected_m2_success_count: int
    selected_m2_rate: Fraction
    pool_m2_rate: Fraction
    m2_delta_vs_pool: Fraction
    random_m2_rate: Fraction
    m2_delta_vs_random: Fraction
    selected_main_hit_sum: int
    selected_avg_match: Fraction
    pool_avg_match: Fraction
    avg_match_delta_vs_pool: Fraction
    random_avg_match: Fraction
    avg_match_delta_vs_random: Fraction
    paired_positive_count: int
    paired_negative_count: int
    paired_tie_count: int

    @property
    def paired_comparison_count(self) -> int:
        return self.paired_positive_count + self.paired_negative_count

    def canonical_dict(self) -> dict[str, object]:
        return {
            "avg_match_delta_vs_pool": exact_fraction_dict(self.avg_match_delta_vs_pool),
            "avg_match_delta_vs_random": exact_fraction_dict(self.avg_match_delta_vs_random),
            "m2_delta_vs_pool": exact_fraction_dict(self.m2_delta_vs_pool),
            "m2_delta_vs_random": exact_fraction_dict(self.m2_delta_vs_random),
            "paired_comparison_count": self.paired_comparison_count,
            "paired_negative_count": self.paired_negative_count,
            "paired_positive_count": self.paired_positive_count,
            "paired_tie_count": self.paired_tie_count,
            "pool_avg_match": exact_fraction_dict(self.pool_avg_match),
            "pool_m2_rate": exact_fraction_dict(self.pool_m2_rate),
            "random_avg_match": exact_fraction_dict(self.random_avg_match),
            "random_m2_rate": exact_fraction_dict(self.random_m2_rate),
            "selected_avg_match": exact_fraction_dict(self.selected_avg_match),
            "selected_m2_rate": exact_fraction_dict(self.selected_m2_rate),
            "selected_m2_success_count": self.selected_m2_success_count,
            "selected_main_hit_sum": self.selected_main_hit_sum,
            "support_count": self.support_count,
        }


def _performance_metrics(series: Sequence[SelectedDraw]) -> PerformanceMetrics:
    _require(bool(series), "performance window is empty")
    support = len(series)
    strategy_counts = {item.strategy_count for item in series}
    _require(len(strategy_counts) == 1, "strategy count changed inside evaluation window")
    strategy_count = next(iter(strategy_counts))
    selected_m2_success_count = sum(item.selected_m2_success for item in series)
    pool_m2_success_count = sum(item.pool_m2_success_count for item in series)
    selected_main_hit_sum = sum(item.selected_main_hit_count for item in series)
    pool_main_hit_sum = sum(item.pool_main_hit_sum for item in series)
    selected_m2_rate = Fraction(selected_m2_success_count, support)
    pool_m2_rate = Fraction(pool_m2_success_count, support * strategy_count)
    selected_avg_match = Fraction(selected_main_hit_sum, support)
    pool_avg_match = Fraction(pool_main_hit_sum, support * strategy_count)

    paired_positive_count = 0
    paired_negative_count = 0
    paired_tie_count = 0
    for item in series:
        signed = item.selected_m2_success * item.strategy_count - item.pool_m2_success_count
        if signed > 0:
            paired_positive_count += 1
        elif signed < 0:
            paired_negative_count += 1
        else:
            paired_tie_count += 1
    return PerformanceMetrics(
        support_count=support,
        selected_m2_success_count=selected_m2_success_count,
        selected_m2_rate=selected_m2_rate,
        pool_m2_rate=pool_m2_rate,
        m2_delta_vs_pool=selected_m2_rate - pool_m2_rate,
        random_m2_rate=SINGLE_TICKET_M2_RANDOM_RATE,
        m2_delta_vs_random=selected_m2_rate - SINGLE_TICKET_M2_RANDOM_RATE,
        selected_main_hit_sum=selected_main_hit_sum,
        selected_avg_match=selected_avg_match,
        pool_avg_match=pool_avg_match,
        avg_match_delta_vs_pool=selected_avg_match - pool_avg_match,
        random_avg_match=SINGLE_TICKET_AVG_MATCH_RANDOM,
        avg_match_delta_vs_random=selected_avg_match - SINGLE_TICKET_AVG_MATCH_RANDOM,
        paired_positive_count=paired_positive_count,
        paired_negative_count=paired_negative_count,
        paired_tie_count=paired_tie_count,
    )


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    rule: InteractionRule
    performance: PerformanceMetrics
    windows: Mapping[int, PerformanceMetrics]
    selection_counts: Mapping[str, int]

    def canonical_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.rule.candidate_id,
            "exact_rule": self.rule.exact_rule,
            "performance": self.performance.canonical_dict(),
            "scope": "R1_DISCOVERY_ONLY",
            "selection_counts": [
                {"count": count, "strategy_id": strategy_id}
                for strategy_id, count in sorted(self.selection_counts.items())
            ],
            "windows": [
                {
                    "performance": self.windows[window].canonical_dict(),
                    "window_draw_count": window,
                }
                for window in TEMPORAL_WINDOW_DRAW_COUNTS
            ],
        }


def evaluate_candidate(
    frames: Sequence[DrawFeatureFrame], rule: InteractionRule
) -> CandidateEvaluation:
    _require(len(frames) == DISCOVERY_DRAW_COUNT, "discovery exposure changed")
    series = _selected_series(frames, rule)
    windows = {
        window: _performance_metrics(series[-window:])
        for window in TEMPORAL_WINDOW_DRAW_COUNTS
    }
    return CandidateEvaluation(
        rule=rule,
        performance=_performance_metrics(series),
        windows=windows,
        selection_counts=Counter(item.selected_strategy_id for item in series),
    )


@dataclass(frozen=True, slots=True)
class TemporalRobustness:
    evaluation: CandidateEvaluation

    @property
    def m2_positive_all_windows(self) -> bool:
        return all(
            self.evaluation.windows[window].m2_delta_vs_pool > 0
            for window in TEMPORAL_WINDOW_DRAW_COUNTS
        )

    @property
    def avg_match_positive_all_windows(self) -> bool:
        return all(
            self.evaluation.windows[window].avg_match_delta_vs_pool > 0
            for window in TEMPORAL_WINDOW_DRAW_COUNTS
        )

    @property
    def passed(self) -> bool:
        return self.m2_positive_all_windows and self.avg_match_positive_all_windows

    def canonical_dict(self) -> dict[str, object]:
        return {
            "avg_match_delta_vs_pool_positive_in_all_windows": (
                self.avg_match_positive_all_windows
            ),
            "gate": (
                "M2_AND_AVG_MATCH_DELTAS_VS_POOL_STRICTLY_POSITIVE_IN_EACH_"
                "TRAILING_50_300_750_DISCOVERY_WINDOW"
            ),
            "m2_delta_vs_pool_positive_in_all_windows": self.m2_positive_all_windows,
            "passed": self.passed,
            "ranking_uses_robustness": False,
            "windows": [
                {
                    "avg_match_delta_vs_pool": exact_fraction_dict(
                        self.evaluation.windows[window].avg_match_delta_vs_pool
                    ),
                    "m2_delta_vs_pool": exact_fraction_dict(
                        self.evaluation.windows[window].m2_delta_vs_pool
                    ),
                    "support_count": self.evaluation.windows[window].support_count,
                    "window_draw_count": window,
                }
                for window in TEMPORAL_WINDOW_DRAW_COUNTS
            ],
        }


@dataclass(frozen=True, slots=True)
class R1DiscoveryAuthority:
    r1_result_sha256: str
    source_database_sha256: str
    source_dataset_identity: str
    source_dataset_sha256: str
    source_run_id: str
    source_run_kind: str
    strategy_ids: tuple[str, ...]
    partition: DiscoveryPartition
    benchmark_candidate_id: str
    benchmark_exact_rule: str
    benchmark_m2_delta_vs_pool: Fraction
    benchmark_avg_match_delta_vs_pool: Fraction

    def canonical_dict(self) -> dict[str, object]:
        return {
            "best_r1_single_feature_rule": {
                "avg_match_delta_vs_pool": exact_fraction_dict(
                    self.benchmark_avg_match_delta_vs_pool
                ),
                "candidate_id": self.benchmark_candidate_id,
                "exact_rule": self.benchmark_exact_rule,
                "m2_delta_vs_pool": exact_fraction_dict(self.benchmark_m2_delta_vs_pool),
            },
            "feature_definitions": [item.canonical_dict() for item in FEATURE_DEFINITIONS],
            "r1_result_sha256": self.r1_result_sha256,
            "source": {
                "database_sha256": self.source_database_sha256,
                "dataset_identity": self.source_dataset_identity,
                "dataset_sha256": self.source_dataset_sha256,
                "run_id": self.source_run_id,
                "run_kind": self.source_run_kind,
                "strategy_ids": list(self.strategy_ids),
            },
            "split": self.partition.canonical_dict(),
        }

    @property
    def projection_sha256(self) -> str:
        return canonical_json.sha256_hex(canonical_json.canonical_bytes(self.canonical_dict()))


def r1_discovery_authority_from_result(
    value: object,
    *,
    r1_result_sha256: str,
) -> R1DiscoveryAuthority:
    """Project only R1 design, source, split, and discovery-winner fields.

    Confirmation results, labels, classification, and promotion fields are not
    accessed by this projection and cannot reach the R2 study API.
    """

    _require(
        _require_sha256(r1_result_sha256, "r1_result_sha256") == PINNED_R1_RESULT_SHA256,
        "R1 result SHA-256 does not match the frozen R2 pin",
    )
    root = _require_mapping(value, "R1 result")
    _require(
        _require_integer(root.get("candidate_rule_count"), "candidate_rule_count") == 36,
        "R1 single-feature candidate count changed",
    )
    candidate_rules = _require_sequence(root.get("candidate_rules"), "candidate_rules")
    _require(len(candidate_rules) == 36, "R1 candidate rule array changed")
    features: dict[str, FeatureDefinition] = {}
    directions: dict[str, set[str]] = {}
    for index, raw_rule in enumerate(candidate_rules):
        rule = _require_mapping(raw_rule, f"candidate_rules[{index}]")
        feature = _require_mapping(rule.get("feature"), f"candidate_rules[{index}].feature")
        definition = FeatureDefinition(
            feature_id=_require_text(feature.get("feature_id"), "feature_id"),
            family=_require_text(feature.get("family"), "feature family"),
            exact_definition=_require_text(
                feature.get("exact_definition"), "feature exact_definition"
            ),
        )
        existing = features.setdefault(definition.feature_id, definition)
        _require(existing == definition, "R1 feature definition changed within candidate rules")
        direction = _require_text(rule.get("selection_direction"), "selection_direction")
        _require(direction in {"ARGMAX", "ARGMIN"}, "R1 feature direction changed")
        directions.setdefault(definition.feature_id, set()).add(direction)
    _require(
        tuple(sorted(features.values())) == FEATURE_DEFINITIONS,
        "R1 feature definitions do not match the frozen 18-feature universe",
    )
    _require(
        all(values == {"ARGMAX", "ARGMIN"} for values in directions.values()),
        "R1 feature directions are not symmetric",
    )

    native = _require_mapping(root.get("native_study_result"), "native_study_result")
    spec = _require_mapping(native.get("spec"), "native_study_result.spec")
    split = _require_mapping(
        spec.get("temporal_holdout_split"),
        "native_study_result.spec.temporal_holdout_split",
    )
    partition = DiscoveryPartition(
        split_method=_require_text(split.get("split_method"), "split_method"),
        total_assignment_count=_require_integer(
            split.get("total_assignment_count"), "total_assignment_count"
        ),
        warmup_count=_require_integer(split.get("warmup_count"), "warmup_count"),
        discovery_count=_require_integer(split.get("discovery_count"), "discovery_count"),
        discovery_first_target=_draw_identity_from_object(
            split.get("discovery_first_target"), "discovery_first_target"
        ),
        discovery_last_target=_draw_identity_from_object(
            split.get("discovery_last_target"), "discovery_last_target"
        ),
    )
    _require(partition == R1_DISCOVERY_PARTITION, "R1 discovery partition identity changed")

    source = _require_mapping(root.get("source"), "source")
    strategy_values = _require_sequence(source.get("strategy_ids"), "source.strategy_ids")
    strategy_ids = tuple(
        _require_text(item, f"source.strategy_ids[{index}]")
        for index, item in enumerate(strategy_values)
    )
    _require(strategy_ids == tuple(sorted(strategy_ids)), "R1 strategy IDs are not sorted")

    frozen_winner = _require_mapping(root.get("frozen_winner"), "frozen_winner")
    discovery = _require_mapping(frozen_winner.get("discovery"), "frozen_winner.discovery")
    performance = _require_mapping(
        discovery.get("performance"), "frozen_winner.discovery.performance"
    )
    _require(
        _require_integer(performance.get("support_count"), "R1 discovery support")
        == DISCOVERY_DRAW_COUNT,
        "R1 best rule discovery support changed",
    )
    benchmark_candidate_id = _require_text(
        discovery.get("candidate_id"), "R1 discovery candidate_id"
    )
    native_winner = _require_mapping(native.get("winner"), "native_study_result.winner")
    _require(
        _require_text(native_winner.get("candidate_id"), "native winner candidate_id")
        == benchmark_candidate_id,
        "R1 discovery winner identities disagree",
    )
    benchmark_m2 = _fraction_from_object(
        performance.get("m2_delta_vs_pool"), "R1 discovery m2_delta_vs_pool"
    )
    benchmark_avg = _fraction_from_object(
        performance.get("avg_match_delta_vs_pool"),
        "R1 discovery avg_match_delta_vs_pool",
    )
    objective_values = _require_sequence(
        native_winner.get("discovery_objective_values"),
        "native winner discovery_objective_values",
    )
    _require(len(objective_values) == 2, "R1 discovery objective shape changed")
    _require(
        _fraction_from_object(objective_values[0], "R1 first discovery objective")
        == benchmark_m2,
        "R1 M2 discovery objective disagrees with frozen winner",
    )
    _require(
        _fraction_from_object(objective_values[1], "R1 second discovery objective")
        == benchmark_avg,
        "R1 average-match discovery objective disagrees with frozen winner",
    )

    return R1DiscoveryAuthority(
        r1_result_sha256=r1_result_sha256,
        source_database_sha256=_require_sha256(
            source.get("database_sha256"), "source.database_sha256"
        ),
        source_dataset_identity=_require_text(
            source.get("dataset_identity"), "source.dataset_identity"
        ),
        source_dataset_sha256=_require_sha256(
            source.get("dataset_sha256"), "source.dataset_sha256"
        ),
        source_run_id=_require_text(source.get("run_id"), "source.run_id"),
        source_run_kind=_require_text(source.get("run_kind"), "source.run_kind"),
        strategy_ids=strategy_ids,
        partition=partition,
        benchmark_candidate_id=benchmark_candidate_id,
        benchmark_exact_rule=_require_text(
            discovery.get("exact_rule"), "R1 discovery exact_rule"
        ),
        benchmark_m2_delta_vs_pool=benchmark_m2,
        benchmark_avg_match_delta_vs_pool=benchmark_avg,
    )


def preregistration_payload(authority: R1DiscoveryAuthority) -> dict[str, object]:
    """Return the complete pre-score design and candidate universe."""

    _require(authority.partition == R1_DISCOVERY_PARTITION, "R1 partition drifted")
    return {
        "anti_leakage_contract": {
            "candidate_universe_frozen_before_scoring": True,
            "confirmation_labels_available_to_selection": False,
            "confirmation_observation_count_loaded": 0,
            "current_target_outcome_used_only_as_label": True,
            "feature_knowledge_cutoff": FEATURE_KNOWLEDGE_CUTOFF,
            "post_discovery_rows_excluded_in_sql": True,
            "r1_confirmation_fields_projected": False,
        },
        "candidate_ranking": {
            "objectives_in_lexicographic_order": [
                "MAXIMIZE_POOLED_DISCOVERY_M2_PLUS_DELTA_VS_POOL_FIRST_TICKET",
                "MAXIMIZE_POOLED_DISCOVERY_AVG_MATCH_DELTA_VS_POOL_FIRST_TICKET",
                "TIE_BREAK_CANONICAL_CANDIDATE_ID_ASC",
            ],
            "pruning": "NONE",
            "robustness_used_for_ranking": False,
            "threshold_learning": "NONE",
        },
        "candidate_universe_sha256": candidate_universe_sha256(),
        "feature_count": FEATURE_COUNT,
        "feature_pair_order": "CANONICAL_R1_FEATURE_NAME_ASC",
        "interaction_candidate_count": INTERACTION_CANDIDATE_COUNT,
        "interaction_rules": [rule.canonical_dict() for rule in INTERACTION_RULES],
        "r1_discovery_authority": authority.canonical_dict(),
        "r1_discovery_authority_sha256": authority.projection_sha256,
        "robustness_gate": {
            "acceptance": (
                "M2_AND_AVG_MATCH_DELTAS_VS_POOL_STRICTLY_POSITIVE_IN_EACH_"
                "TRAILING_50_300_750_DISCOVERY_WINDOW"
            ),
            "pooled_score_reported_separately": True,
            "ranking_uses_gate": False,
            "window_draw_counts": list(TEMPORAL_WINDOW_DRAW_COUNTS),
        },
        "schema_id": PREREGISTRATION_SCHEMA_ID,
        "schema_version": PREREGISTRATION_SCHEMA_VERSION,
        "selection_semantics": {
            "final_tie_breaker": FINAL_TIE_BREAKER,
            "primary_key": "FEATURE_A",
            "secondary_key_only_resolves_equal_primary": "FEATURE_B",
            "selection_unit": SELECTION_UNIT,
        },
        "study_id": STUDY_ID,
    }


def _discovery_frames(
    corpus: HistoricalReplayDiscoveryCorpus,
    partition: DiscoveryPartition,
) -> tuple[DrawFeatureFrame, ...]:
    _require(
        len(corpus.draws) == partition.source_draw_count,
        "corpus must end at the discovery boundary with no confirmation rows",
    )
    _require(
        corpus.draws[partition.warmup_count].target == partition.discovery_first_target,
        "discovery first-target identity changed",
    )
    _require(
        corpus.draws[-1].target == partition.discovery_last_target,
        "discovery last-target identity changed",
    )
    all_frames = build_feature_frames(corpus)
    by_target = {frame.draw.target: frame for frame in all_frames}
    discovery_draws = corpus.draws[partition.warmup_count :]
    selected = tuple(by_target[draw.target] for draw in discovery_draws)
    _require(len(selected) == partition.discovery_count, "discovery frame count changed")
    return selected


def _evaluation_sort_key(value: CandidateEvaluation) -> tuple[Fraction, Fraction, str]:
    return (
        -value.performance.m2_delta_vs_pool,
        -value.performance.avg_match_delta_vs_pool,
        value.rule.candidate_id,
    )


@dataclass(frozen=True, slots=True)
class InteractionDiscoveryExecution:
    corpus: HistoricalReplayDiscoveryCorpus
    database_sha256: str
    preregistration_sha256: str
    authority: R1DiscoveryAuthority
    evaluations: tuple[CandidateEvaluation, ...]
    winner: CandidateEvaluation
    pooled_winner: CandidateEvaluation
    robust_candidate_count: int
    top_discovery_candidates: tuple[CandidateEvaluation, ...]
    temporal_robustness: TemporalRobustness
    final_classification: FinalClassification
    classification_reason: str

    @property
    def completed_count(self) -> int:
        return len(self.evaluations)

    def canonical_dict(self) -> dict[str, object]:
        winner_metrics = self.winner.performance
        return {
            "anti_leakage_contract": {
                "candidate_construction_uses_r1_confirmation": False,
                "confirmation_observation_count_loaded": 0,
                "post_discovery_rows_excluded_in_sql": True,
                "r1_confirmation_fields_accessed_for_selection": False,
                "result_classification_uses_r1_confirmation": False,
                "selection_scope": "R1_750_DRAW_DISCOVERY_ONLY",
            },
            "best_discovery_interaction": self.winner.rule.canonical_dict(),
            "best_pooled_discovery_interaction": self.pooled_winner.rule.canonical_dict(),
            "candidate_universe_sha256": candidate_universe_sha256(),
            "classification_reason": self.classification_reason,
            "completed_count": self.completed_count,
            "corpus_profile": self.corpus.profile.canonical_dict(),
            "delta_vs_best_r1_single_feature_rule": {
                "avg_match_delta_vs_pool_difference": exact_fraction_dict(
                    winner_metrics.avg_match_delta_vs_pool
                    - self.authority.benchmark_avg_match_delta_vs_pool
                ),
                "m2_delta_vs_pool_difference": exact_fraction_dict(
                    winner_metrics.m2_delta_vs_pool
                    - self.authority.benchmark_m2_delta_vs_pool
                ),
                "r1_candidate_id": self.authority.benchmark_candidate_id,
                "r1_discovery_avg_match_delta_vs_pool": exact_fraction_dict(
                    self.authority.benchmark_avg_match_delta_vs_pool
                ),
                "r1_discovery_m2_delta_vs_pool": exact_fraction_dict(
                    self.authority.benchmark_m2_delta_vs_pool
                ),
                "r2_discovery_avg_match_delta_vs_pool": exact_fraction_dict(
                    winner_metrics.avg_match_delta_vs_pool
                ),
                "r2_discovery_m2_delta_vs_pool": exact_fraction_dict(
                    winner_metrics.m2_delta_vs_pool
                ),
            },
            "discovery_result": self.winner.canonical_dict(),
            "failed_count": 0,
            "feature_count": FEATURE_COUNT,
            "final_classification": self.final_classification.value,
            "future_confirmation_status": "REQUIRES_FRESH_UNSEEN_DATA",
            "interaction_candidate_count": INTERACTION_CANDIDATE_COUNT,
            "preregistration_sha256": self.preregistration_sha256,
            "production_promotion": "NOT_AUTHORIZED_NOT_PERFORMED",
            "promotion_decision": "NOT_AUTHORIZED",
            "pruned_count": 0,
            "r1_discovery_authority": self.authority.canonical_dict(),
            "r1_discovery_authority_sha256": self.authority.projection_sha256,
            "schema_id": RESULT_SCHEMA_ID,
            "schema_version": RESULT_SCHEMA_VERSION,
            "robust_candidate_count": self.robust_candidate_count,
            "source": {
                "database_sha256": self.database_sha256,
                "dataset_identity": self.corpus.source_dataset_identity,
                "dataset_sha256": self.corpus.source_dataset_sha256,
                "discovery_partition": self.authority.partition.canonical_dict(),
                "latest_run_status": self.corpus.latest_run_status,
                "rule_contract_id": self.corpus.source_rule_contract_id,
                "run_id": self.corpus.source_run_id,
                "run_kind": self.corpus.source_run_kind,
                "sample_loaded_targets": [
                    self.corpus.draws[0].target.canonical_dict(),
                    self.corpus.draws[self.authority.partition.warmup_count].target.canonical_dict(),
                    self.corpus.draws[-1].target.canonical_dict(),
                ],
                "strategy_ids": list(self.corpus.strategies),
            },
            "study_id": STUDY_ID,
            "temporal_robustness": self.temporal_robustness.canonical_dict(),
            "pooled_discovery_result": self.pooled_winner.canonical_dict(),
            "top_discovery_candidates": [
                item.canonical_dict() for item in self.top_discovery_candidates
            ],
            "trials": [item.canonical_dict() for item in self.evaluations],
        }


def run_interaction_discovery(
    corpus: HistoricalReplayDiscoveryCorpus,
    *,
    database_sha256: str,
    preregistration_sha256: str,
    authority: R1DiscoveryAuthority,
) -> InteractionDiscoveryExecution:
    """Evaluate every frozen rule using only the bounded R1 discovery corpus."""

    _require_sha256(database_sha256, "database_sha256")
    _require_sha256(preregistration_sha256, "preregistration_sha256")
    _require(database_sha256 == authority.source_database_sha256, "database authority changed")
    _require(corpus.source_run_id == authority.source_run_id, "source run changed")
    _require(corpus.source_run_kind == authority.source_run_kind, "source run kind changed")
    _require(
        corpus.source_dataset_identity == authority.source_dataset_identity,
        "source dataset identity changed",
    )
    _require(
        corpus.source_dataset_sha256 == authority.source_dataset_sha256,
        "source dataset SHA-256 changed",
    )
    _require(corpus.strategies == authority.strategy_ids, "source strategy universe changed")
    frames = _discovery_frames(corpus, authority.partition)
    evaluations = tuple(evaluate_candidate(frames, rule) for rule in INTERACTION_RULES)
    _require(
        len(evaluations) == INTERACTION_CANDIDATE_COUNT,
        "not every frozen candidate completed",
    )
    ranked = tuple(sorted(evaluations, key=_evaluation_sort_key))
    pooled_winner = ranked[0]
    robust_ranked = tuple(item for item in ranked if TemporalRobustness(item).passed)
    winner = robust_ranked[0] if robust_ranked else pooled_winner
    robustness = TemporalRobustness(winner)
    if robust_ranked:
        classification = FinalClassification.DISCOVERY_ONLY_CANDIDATE_FROZEN
        reason = (
            "the highest pooled-ranked interaction satisfying the separately frozen "
            "robustness gate has strictly positive M2 and average-match deltas versus "
            "the pooled first-ticket baseline in each trailing 50/300/750 discovery "
            "window; no confirmation claim is made"
        )
    else:
        classification = FinalClassification.NO_ROBUST_DISCOVERY_CANDIDATE
        reason = (
            "none of the 612 fully evaluated interactions satisfies the separately frozen "
            "positive M2 and average-match delta gate in every trailing 50/300/750 "
            "discovery window"
        )
    return InteractionDiscoveryExecution(
        corpus=corpus,
        database_sha256=database_sha256,
        preregistration_sha256=preregistration_sha256,
        authority=authority,
        evaluations=evaluations,
        winner=winner,
        pooled_winner=pooled_winner,
        robust_candidate_count=len(robust_ranked),
        top_discovery_candidates=ranked[:TOP_DISCOVERY_CANDIDATE_COUNT],
        temporal_robustness=robustness,
        final_classification=classification,
        classification_reason=reason,
    )


__all__ = [
    "DISCOVERY_DRAW_COUNT",
    "FEATURE_COUNT",
    "FEATURE_DEFINITIONS",
    "INTERACTION_CANDIDATE_COUNT",
    "INTERACTION_RULES",
    "PINNED_R1_RESULT_SHA256",
    "R1_DISCOVERY_PARTITION",
    "TEMPORAL_WINDOW_DRAW_COUNTS",
    "CandidateEvaluation",
    "CorpusDraw",
    "CorpusProfile",
    "DiscoveryPartition",
    "DrawFeatureFrame",
    "DrawIdentity",
    "FinalClassification",
    "HistoricalReplayDiscoveryCorpus",
    "InteractionDiscoveryError",
    "InteractionDiscoveryExecution",
    "InteractionRule",
    "PerformanceMetrics",
    "R1DiscoveryAuthority",
    "RunInventory",
    "SelectionDirection",
    "StrategyPrediction",
    "StrategyTargetObservation",
    "TemporalRobustness",
    "TicketPrediction",
    "build_feature_frames",
    "candidate_universe_sha256",
    "evaluate_candidate",
    "exact_fraction_dict",
    "exact_fraction_text",
    "preregistration_payload",
    "r1_discovery_authority_from_result",
    "run_interaction_discovery",
    "select_strategy",
]
