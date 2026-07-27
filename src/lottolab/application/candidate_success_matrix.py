"""Pure Candidate-K success matrices over immutable ordered observations.

R1 implements ``CANDIDATE_COVERAGE`` only.  Candidate coverage is never
reinterpreted as a legal-ticket prize or an official prize tier.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from math import comb, gcd

from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_evidence import (
    CandidateCoverageOutcome,
    OrderedCandidateObservation,
    candidate_game_rule,
    evaluate_candidate_coverage,
)
from lottolab.domain.strategy_success_evaluation import (
    WindowEvaluationStatus,
    WindowKind,
)
from lottolab.domain.strategy_success_measurement import (
    DEFAULT_WINDOW_POLICY,
    MeasurementMode,
    MeasurementWindowPolicy,
    WindowRole,
)


class CandidateSuccessMatrixInputError(ValueError):
    """The immutable source sequence cannot be safely evaluated."""


class CandidateCoverageCriterion(StrEnum):
    M1_PLUS = "M1_PLUS"
    M2_PLUS = "M2_PLUS"
    M3_PLUS = "M3_PLUS"
    M4_PLUS = "M4_PLUS"
    M5_PLUS = "M5_PLUS"
    M6_PLUS = "M6_PLUS"
    SPECIAL_HIT = "SPECIAL_HIT"
    M2_PLUS_SPECIAL = "M2_PLUS_SPECIAL"
    M3_PLUS_SPECIAL = "M3_PLUS_SPECIAL"
    M4_PLUS_SPECIAL = "M4_PLUS_SPECIAL"
    M5_PLUS_SPECIAL = "M5_PLUS_SPECIAL"
    M6_PLUS_SPECIAL = "M6_PLUS_SPECIAL"
    ZONE2_HIT = "ZONE2_HIT"
    M1_PLUS_ZONE2 = "M1_PLUS_ZONE2"
    M2_PLUS_ZONE2 = "M2_PLUS_ZONE2"
    M3_PLUS_ZONE2 = "M3_PLUS_ZONE2"
    M4_PLUS_ZONE2 = "M4_PLUS_ZONE2"
    M5_PLUS_ZONE2 = "M5_PLUS_ZONE2"
    M6_PLUS_ZONE2 = "M6_PLUS_ZONE2"


class BaselineRelation(StrEnum):
    ABOVE = "ABOVE_RANDOM"
    EQUAL = "EQUAL_RANDOM"
    BELOW = "BELOW_RANDOM"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


_MAIN_CRITERIA = (
    CandidateCoverageCriterion.M1_PLUS,
    CandidateCoverageCriterion.M2_PLUS,
    CandidateCoverageCriterion.M3_PLUS,
    CandidateCoverageCriterion.M4_PLUS,
    CandidateCoverageCriterion.M5_PLUS,
    CandidateCoverageCriterion.M6_PLUS,
)
_BIG_SPECIAL_CRITERIA = (
    CandidateCoverageCriterion.M2_PLUS_SPECIAL,
    CandidateCoverageCriterion.M3_PLUS_SPECIAL,
    CandidateCoverageCriterion.M4_PLUS_SPECIAL,
    CandidateCoverageCriterion.M5_PLUS_SPECIAL,
    CandidateCoverageCriterion.M6_PLUS_SPECIAL,
)
_POWER_ZONE2_CRITERIA = (
    CandidateCoverageCriterion.M1_PLUS_ZONE2,
    CandidateCoverageCriterion.M2_PLUS_ZONE2,
    CandidateCoverageCriterion.M3_PLUS_ZONE2,
    CandidateCoverageCriterion.M4_PLUS_ZONE2,
    CandidateCoverageCriterion.M5_PLUS_ZONE2,
    CandidateCoverageCriterion.M6_PLUS_ZONE2,
)


def supported_criteria(
    lottery_type: LotteryType,
) -> tuple[CandidateCoverageCriterion, ...]:
    rule = candidate_game_rule(lottery_type)
    mains = _MAIN_CRITERIA[: rule.main_draw_count]
    if lottery_type is LotteryType.BIG_LOTTO:
        return (*mains, CandidateCoverageCriterion.SPECIAL_HIT, *_BIG_SPECIAL_CRITERIA)
    if lottery_type is LotteryType.POWER_LOTTO:
        return (*mains, CandidateCoverageCriterion.ZONE2_HIT, *_POWER_ZONE2_CRITERIA)
    return mains


def _criterion_main_threshold(criterion: CandidateCoverageCriterion) -> int | None:
    values = {
        CandidateCoverageCriterion.M1_PLUS: 1,
        CandidateCoverageCriterion.M2_PLUS: 2,
        CandidateCoverageCriterion.M3_PLUS: 3,
        CandidateCoverageCriterion.M4_PLUS: 4,
        CandidateCoverageCriterion.M5_PLUS: 5,
        CandidateCoverageCriterion.M6_PLUS: 6,
        CandidateCoverageCriterion.M2_PLUS_SPECIAL: 2,
        CandidateCoverageCriterion.M3_PLUS_SPECIAL: 3,
        CandidateCoverageCriterion.M4_PLUS_SPECIAL: 4,
        CandidateCoverageCriterion.M5_PLUS_SPECIAL: 5,
        CandidateCoverageCriterion.M6_PLUS_SPECIAL: 6,
        CandidateCoverageCriterion.M1_PLUS_ZONE2: 1,
        CandidateCoverageCriterion.M2_PLUS_ZONE2: 2,
        CandidateCoverageCriterion.M3_PLUS_ZONE2: 3,
        CandidateCoverageCriterion.M4_PLUS_ZONE2: 4,
        CandidateCoverageCriterion.M5_PLUS_ZONE2: 5,
        CandidateCoverageCriterion.M6_PLUS_ZONE2: 6,
    }
    return values.get(criterion)


@dataclass(frozen=True, slots=True)
class ExactRational:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise ValueError("exact rational operands must be integers")
        if self.numerator < 0 or self.denominator <= 0 or self.numerator > self.denominator:
            raise ValueError("exact rational must be a probability in [0, 1]")
        divisor = gcd(self.numerator, self.denominator)
        object.__setattr__(self, "numerator", self.numerator // divisor)
        object.__setattr__(self, "denominator", self.denominator // divisor)

    @classmethod
    def from_fraction(cls, value: Fraction) -> ExactRational:
        return cls(value.numerator, value.denominator)

    def as_fraction(self) -> Fraction:
        return Fraction(self.numerator, self.denominator)

    def canonical_dict(self) -> dict[str, int]:
        return {
            "denominator": self.denominator,
            "numerator": self.numerator,
        }


@dataclass(frozen=True, slots=True)
class ExactObservedRate:
    """Unreduced integer evidence counts; ``0/0`` is explicitly unavailable."""

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise ValueError("observed-rate operands must be integers")
        if (
            self.numerator < 0
            or self.denominator < 0
            or self.numerator > self.denominator
        ):
            raise ValueError("observed-rate counts are contradictory")

    @property
    def is_available(self) -> bool:
        return self.denominator > 0

    def as_fraction(self) -> Fraction | None:
        if not self.is_available:
            return None
        return Fraction(self.numerator, self.denominator)

    def canonical_dict(self) -> dict[str, int | bool]:
        return {
            "available": self.is_available,
            "denominator": self.denominator,
            "numerator": self.numerator,
        }


@dataclass(frozen=True, slots=True)
class EffectiveUniqueKCount:
    effective_unique_k: int
    observation_count: int

    def __post_init__(self) -> None:
        if type(self.effective_unique_k) is not int or self.effective_unique_k < 1:
            raise ValueError("effective_unique_k must be positive")
        if type(self.observation_count) is not int or self.observation_count < 1:
            raise ValueError("observation_count must be positive")

    def canonical_dict(self) -> dict[str, int]:
        return {
            "effective_unique_k": self.effective_unique_k,
            "observation_count": self.observation_count,
        }


@dataclass(frozen=True, slots=True)
class CandidateSuccessMatrixCell:
    lottery_type: LotteryType
    strategy_id: str
    strategy_version: str
    replicate: int
    measurement_mode: MeasurementMode
    requested_k: int
    criterion: CandidateCoverageCriterion
    window_kind: WindowKind
    window_role: WindowRole
    requested_draw_count: int | None
    source_observation_count: int
    eligible_observation_count: int
    excluded_observation_count: int
    success_rate: ExactObservedRate
    random_baseline: ExactRational | None
    observed_minus_baseline: BaselineRelation | None
    effective_unique_k_counts: tuple[EffectiveUniqueKCount, ...]
    first_target_draw: str
    last_target_draw: str
    evaluation_status: WindowEvaluationStatus
    nested_windows_independent: bool
    window_policy_version: str

    def __post_init__(self) -> None:
        if self.measurement_mode is not MeasurementMode.CANDIDATE_COVERAGE:
            raise ValueError("R1 matrix cells must remain CANDIDATE_COVERAGE")
        if self.criterion not in supported_criteria(self.lottery_type):
            raise ValueError("criterion does not belong to the cell lottery")
        rule = candidate_game_rule(self.lottery_type)
        if type(self.requested_k) is not int or not 1 <= self.requested_k <= rule.candidate_k_max:
            raise ValueError("requested_k is outside the game-specific range")
        for name in (
            "source_observation_count",
            "eligible_observation_count",
            "excluded_observation_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be non-negative")
        if (
            self.source_observation_count
            != self.eligible_observation_count + self.excluded_observation_count
        ):
            raise ValueError("source observations must equal eligible plus excluded")
        if self.success_rate.denominator != self.eligible_observation_count:
            raise ValueError("success-rate denominator must equal eligible observations")
        if sum(item.observation_count for item in self.effective_unique_k_counts) != (
            self.source_observation_count
        ):
            raise ValueError("effective-K distribution must cover the source window")
        if tuple(item.effective_unique_k for item in self.effective_unique_k_counts) != tuple(
            sorted(item.effective_unique_k for item in self.effective_unique_k_counts)
        ):
            raise ValueError("effective-K distribution must use canonical ascending order")
        if self.eligible_observation_count == 0:
            if self.random_baseline is not None or self.observed_minus_baseline is not None:
                raise ValueError("an unavailable cell cannot expose baseline comparison")
        else:
            if (
                type(self.random_baseline) is not ExactRational
                or type(self.observed_minus_baseline) is not BaselineRelation
            ):
                raise ValueError("an eligible cell requires an exact baseline comparison")
        if self.nested_windows_independent:
            raise ValueError("nested evidence windows are not independent replications")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "criterion": self.criterion.value,
            "effective_unique_k_counts": [
                item.canonical_dict() for item in self.effective_unique_k_counts
            ],
            "eligible_observation_count": self.eligible_observation_count,
            "evaluation_status": self.evaluation_status.value,
            "excluded_observation_count": self.excluded_observation_count,
            "first_target_draw": self.first_target_draw,
            "last_target_draw": self.last_target_draw,
            "lottery_type": self.lottery_type.value,
            "measurement_mode": self.measurement_mode.value,
            "nested_windows_independent": self.nested_windows_independent,
            "observed_minus_baseline": (
                None
                if self.observed_minus_baseline is None
                else self.observed_minus_baseline.value
            ),
            "random_baseline": (
                None if self.random_baseline is None else self.random_baseline.canonical_dict()
            ),
            "replicate": self.replicate,
            "requested_draw_count": self.requested_draw_count,
            "requested_k": self.requested_k,
            "source_observation_count": self.source_observation_count,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "success_rate": self.success_rate.canonical_dict(),
            "window_kind": self.window_kind.value,
            "window_policy_version": self.window_policy_version,
            "window_role": self.window_role.value,
        }


@dataclass(frozen=True, slots=True)
class CandidateSuccessMatrix:
    lottery_type: LotteryType
    strategy_id: str
    strategy_version: str
    replicate: int
    measurement_mode: MeasurementMode
    source_observation_count: int
    requested_candidate_ks: tuple[int, ...]
    criteria: tuple[CandidateCoverageCriterion, ...]
    cells: tuple[CandidateSuccessMatrixCell, ...]
    window_policy: MeasurementWindowPolicy

    def __post_init__(self) -> None:
        if self.measurement_mode is not MeasurementMode.CANDIDATE_COVERAGE:
            raise ValueError("R1 matrix must remain CANDIDATE_COVERAGE")
        if type(self.window_policy) is not MeasurementWindowPolicy:
            raise ValueError("window_policy is malformed")
        expected_cell_count = 4 * len(self.requested_candidate_ks) * len(self.criteria)
        if len(self.cells) != expected_cell_count:
            raise ValueError("matrix cell cardinality is incomplete")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "cells": [cell.canonical_dict() for cell in self.cells],
            "criteria": [criterion.value for criterion in self.criteria],
            "lottery_type": self.lottery_type.value,
            "measurement_mode": self.measurement_mode.value,
            "replicate": self.replicate,
            "requested_candidate_ks": list(self.requested_candidate_ks),
            "source_observation_count": self.source_observation_count,
            "strategy_id": self.strategy_id,
            "strategy_version": self.strategy_version,
            "window_policy": self.window_policy.canonical_dict(),
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


def _safe_comb(n: int, k: int) -> int:
    if n < 0 or k < 0 or k > n:
        return 0
    return comb(n, k)


def _main_hit_probability(
    *,
    pool_size: int,
    drawn_count: int,
    selected_count: int,
    minimum_hits: int,
) -> Fraction:
    denominator = _safe_comb(pool_size, selected_count)
    numerator = sum(
        _safe_comb(drawn_count, hits)
        * _safe_comb(pool_size - drawn_count, selected_count - hits)
        for hits in range(minimum_hits, min(drawn_count, selected_count) + 1)
    )
    return Fraction(numerator, denominator)


def candidate_random_baseline(
    *,
    lottery_type: LotteryType,
    effective_unique_k: int,
    criterion: CandidateCoverageCriterion,
    zone2_operand_present: bool = True,
) -> ExactRational | None:
    """Return one game-specific exact baseline without cross-game pooling."""

    rule = candidate_game_rule(lottery_type)
    if criterion not in supported_criteria(lottery_type):
        raise ValueError("criterion does not belong to lottery_type")
    if (
        type(effective_unique_k) is not int
        or not 1 <= effective_unique_k <= rule.candidate_k_max
    ):
        raise ValueError("effective_unique_k is outside the game-specific range")
    if type(zone2_operand_present) is not bool:
        raise ValueError("zone2_operand_present must be a boolean")

    threshold = _criterion_main_threshold(criterion)
    if criterion in _MAIN_CRITERIA:
        if threshold is None:
            raise AssertionError("main criterion lost its threshold")
        probability = _main_hit_probability(
            pool_size=rule.main_pool_size,
            drawn_count=rule.main_draw_count,
            selected_count=effective_unique_k,
            minimum_hits=threshold,
        )
    elif criterion is CandidateCoverageCriterion.SPECIAL_HIT:
        probability = Fraction(effective_unique_k, 49)
    elif criterion in _BIG_SPECIAL_CRITERIA:
        if threshold is None:
            raise AssertionError("special criterion lost its threshold")
        denominator = _safe_comb(49, effective_unique_k)
        numerator = sum(
            _safe_comb(6, hits) * _safe_comb(42, effective_unique_k - hits - 1)
            for hits in range(threshold, min(6, effective_unique_k - 1) + 1)
        )
        probability = Fraction(numerator, denominator)
    elif criterion is CandidateCoverageCriterion.ZONE2_HIT:
        if not zone2_operand_present:
            return None
        probability = Fraction(1, 8)
    else:
        if not zone2_operand_present:
            return None
        if threshold is None:
            raise AssertionError("zone-2 criterion lost its threshold")
        probability = _main_hit_probability(
            pool_size=38,
            drawn_count=6,
            selected_count=effective_unique_k,
            minimum_hits=threshold,
        ) * Fraction(1, 8)
    return ExactRational.from_fraction(probability)


def _criterion_succeeded(
    outcome: CandidateCoverageOutcome,
    criterion: CandidateCoverageCriterion,
) -> bool | None:
    threshold = _criterion_main_threshold(criterion)
    if criterion in _MAIN_CRITERIA:
        if threshold is None:
            raise AssertionError("main criterion lost its threshold")
        return outcome.main_hits >= threshold
    if criterion is CandidateCoverageCriterion.SPECIAL_HIT:
        return outcome.special_hit
    if criterion in _BIG_SPECIAL_CRITERIA:
        if threshold is None:
            raise AssertionError("special criterion lost its threshold")
        return outcome.main_hits >= threshold and outcome.special_hit is True
    if criterion is CandidateCoverageCriterion.ZONE2_HIT:
        return outcome.zone2_hit
    if threshold is None:
        raise AssertionError("zone-2 criterion lost its threshold")
    if outcome.zone2_hit is None:
        return None
    return outcome.main_hits >= threshold and outcome.zone2_hit


def _validated_observations(
    observations: tuple[OrderedCandidateObservation, ...],
    window_policy: MeasurementWindowPolicy,
) -> tuple[OrderedCandidateObservation, ...]:
    if type(observations) is not tuple or not observations:
        raise CandidateSuccessMatrixInputError(
            "observations must be a non-empty immutable tuple"
        )
    if any(type(item) is not OrderedCandidateObservation for item in observations):
        raise CandidateSuccessMatrixInputError("observations contains a malformed item")
    if type(window_policy) is not MeasurementWindowPolicy:
        raise CandidateSuccessMatrixInputError("window_policy is malformed")

    first = observations[0]
    target_draws: set[str] = set()
    for item in observations:
        if item.target_draw in target_draws:
            raise CandidateSuccessMatrixInputError(
                f"duplicate target identity: {item.target_draw}"
            )
        target_draws.add(item.target_draw)
        if item.lottery_type is not first.lottery_type:
            raise CandidateSuccessMatrixInputError("observations mix lottery identity")
        if item.strategy_identity != first.strategy_identity:
            raise CandidateSuccessMatrixInputError("observations mix strategy identity")
        if item.duplicate_handling_policy is not first.duplicate_handling_policy:
            raise CandidateSuccessMatrixInputError("observations mix duplicate policy")
        if item.window_policy_version != window_policy.policy_version:
            raise CandidateSuccessMatrixInputError(
                "observation window policy version does not match evaluation policy"
            )
    return observations


def _window_specs(
    policy: MeasurementWindowPolicy,
) -> tuple[tuple[WindowKind, WindowRole, int | None], ...]:
    return (
        (WindowKind.FULL_HISTORY, policy.full_history_role, None),
        (WindowKind.LONG, policy.long_role, policy.long_draws),
        (WindowKind.MEDIUM, policy.medium_role, policy.medium_draws),
        (WindowKind.SHORT, policy.short_role, policy.short_draws),
    )


def _relation(observed: Fraction, baseline: Fraction) -> BaselineRelation:
    if observed > baseline:
        return BaselineRelation.ABOVE
    if observed < baseline:
        return BaselineRelation.BELOW
    return BaselineRelation.EQUAL


def evaluate_candidate_success_matrix(
    observations: tuple[OrderedCandidateObservation, ...],
    *,
    window_policy: MeasurementWindowPolicy = DEFAULT_WINDOW_POLICY,
) -> CandidateSuccessMatrix:
    """Evaluate every supported K/criterion over nested source-order suffixes."""

    source = _validated_observations(observations, window_policy)
    first = source[0]
    rule = candidate_game_rule(first.lottery_type)
    requested_ks = tuple(range(1, rule.candidate_k_max + 1))
    criteria = supported_criteria(first.lottery_type)
    outcomes = {
        (item.target_draw, requested_k): evaluate_candidate_coverage(item, requested_k)
        for item in source
        for requested_k in requested_ks
    }
    cells: list[CandidateSuccessMatrixCell] = []

    for kind, role, requested_draw_count in _window_specs(window_policy):
        window = source if requested_draw_count is None else source[-requested_draw_count:]
        for requested_k in requested_ks:
            window_outcomes = tuple(
                outcomes[(item.target_draw, requested_k)] for item in window
            )
            effective_counts: dict[int, int] = {}
            for outcome in window_outcomes:
                effective = outcome.selection.effective_unique_k
                effective_counts[effective] = effective_counts.get(effective, 0) + 1
            distribution = tuple(
                EffectiveUniqueKCount(effective, count)
                for effective, count in sorted(effective_counts.items())
            )

            for criterion in criteria:
                evaluated = tuple(
                    _criterion_succeeded(outcome, criterion)
                    for outcome in window_outcomes
                )
                eligible_indexes = tuple(
                    index for index, result in enumerate(evaluated) if result is not None
                )
                excluded = len(window) - len(eligible_indexes)
                successes = sum(evaluated[index] is True for index in eligible_indexes)
                success_rate = ExactObservedRate(successes, len(eligible_indexes))

                if requested_draw_count is not None and len(window) < requested_draw_count:
                    status = WindowEvaluationStatus.INSUFFICIENT_DRAWS
                elif not eligible_indexes:
                    status = WindowEvaluationStatus.NO_ELIGIBLE_DRAWS
                else:
                    status = WindowEvaluationStatus.COMPLETE

                baseline: ExactRational | None = None
                relation: BaselineRelation | None = None
                if eligible_indexes:
                    baseline_values: list[Fraction] = []
                    for index in eligible_indexes:
                        outcome = window_outcomes[index]
                        exact = candidate_random_baseline(
                            lottery_type=first.lottery_type,
                            effective_unique_k=outcome.selection.effective_unique_k,
                            criterion=criterion,
                            zone2_operand_present=outcome.zone2_hit is not None,
                        )
                        if exact is None:
                            raise AssertionError("eligible outcome lost its exact baseline")
                        baseline_values.append(exact.as_fraction())
                    baseline_fraction = sum(baseline_values, start=Fraction()) / len(
                        baseline_values
                    )
                    baseline = ExactRational.from_fraction(baseline_fraction)
                    observed_fraction = success_rate.as_fraction()
                    if observed_fraction is None:
                        raise AssertionError("eligible cell lost its exact observed rate")
                    relation = _relation(observed_fraction, baseline_fraction)

                cells.append(
                    CandidateSuccessMatrixCell(
                        lottery_type=first.lottery_type,
                        strategy_id=first.strategy_id,
                        strategy_version=first.strategy_version,
                        replicate=first.replicate,
                        measurement_mode=MeasurementMode.CANDIDATE_COVERAGE,
                        requested_k=requested_k,
                        criterion=criterion,
                        window_kind=kind,
                        window_role=role,
                        requested_draw_count=requested_draw_count,
                        source_observation_count=len(window),
                        eligible_observation_count=len(eligible_indexes),
                        excluded_observation_count=excluded,
                        success_rate=success_rate,
                        random_baseline=baseline,
                        observed_minus_baseline=relation,
                        effective_unique_k_counts=distribution,
                        first_target_draw=window[0].target_draw,
                        last_target_draw=window[-1].target_draw,
                        evaluation_status=status,
                        nested_windows_independent=window_policy.nested_windows_independent,
                        window_policy_version=window_policy.policy_version,
                    )
                )

    return CandidateSuccessMatrix(
        lottery_type=first.lottery_type,
        strategy_id=first.strategy_id,
        strategy_version=first.strategy_version,
        replicate=first.replicate,
        measurement_mode=MeasurementMode.CANDIDATE_COVERAGE,
        source_observation_count=len(source),
        requested_candidate_ks=requested_ks,
        criteria=criteria,
        cells=tuple(cells),
        window_policy=window_policy,
    )


__all__ = [
    "BaselineRelation",
    "CandidateCoverageCriterion",
    "CandidateSuccessMatrix",
    "CandidateSuccessMatrixCell",
    "CandidateSuccessMatrixInputError",
    "EffectiveUniqueKCount",
    "ExactObservedRate",
    "ExactRational",
    "candidate_random_baseline",
    "evaluate_candidate_success_matrix",
    "supported_criteria",
]
