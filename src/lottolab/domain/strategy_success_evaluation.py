"""Pure evaluation of source-ordered strategy-success measurement windows.

This module classifies already-measured per-draw outcomes and summarizes the
nested full/750/300/50 windows.  It does not load history, infer selection
identity from names, rank strategies, or make promotion decisions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeGuard

from lottolab.domain.draws import LotteryType
from lottolab.domain.strategy_success_measurement import (
    BigLottoOutcomeSignature,
    Daily539OutcomeSignature,
    EvidenceStatus,
    MeasurementMode,
    MeasurementWindowPolicy,
    OutcomeEligibility,
    PowerLottoOutcomeSignature,
    SelectionIdentity,
    StrategySuccessMeasurement,
    WindowRole,
)


class StrategySuccessEvaluationInputError(ValueError):
    """The source sequence cannot be evaluated without repairing its identity."""


class ObservationEvaluation(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    EXCLUDED = "EXCLUDED"


class WindowKind(StrEnum):
    FULL_HISTORY = "FULL_HISTORY"
    LONG = "LONG"
    MEDIUM = "MEDIUM"
    SHORT = "SHORT"


class WindowEvaluationStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INSUFFICIENT_DRAWS = "INSUFFICIENT_DRAWS"
    NO_ELIGIBLE_DRAWS = "NO_ELIGIBLE_DRAWS"


class PowerLottoZone2Requirement(StrEnum):
    NOT_USED = "NOT_USED"
    HIT_REQUIRED = "HIT_REQUIRED"
    MISS_REQUIRED = "MISS_REQUIRED"


def _require_diagnostic_mode(mode: MeasurementMode) -> None:
    if type(mode) is not MeasurementMode:
        raise ValueError("expected_mode must be a MeasurementMode")
    if mode is MeasurementMode.OFFICIAL_PRIZE_TIER:
        raise ValueError("diagnostic criteria cannot use OFFICIAL_PRIZE_TIER mode")


def _canonical_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True, slots=True)
class ExactSuccessRate:
    """An exact success fraction; ``0/0`` is the explicit unavailable state."""

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if type(self.numerator) is not int or type(self.denominator) is not int:
            raise ValueError("success-rate numerator and denominator must be integers")
        if self.numerator < 0 or self.denominator < 0:
            raise ValueError("success-rate counts must be non-negative")
        if self.numerator > self.denominator:
            raise ValueError("success-rate numerator cannot exceed denominator")

    @classmethod
    def unavailable(cls) -> ExactSuccessRate:
        return cls(0, 0)

    @property
    def is_available(self) -> bool:
        return self.denominator > 0

    def canonical_dict(self) -> dict[str, object]:
        return {
            "available": self.is_available,
            "denominator": self.denominator,
            "numerator": self.numerator,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class BigLottoSuccessCriterion:
    minimum_main_hits: int
    require_special_hit: bool
    expected_mode: MeasurementMode

    def __post_init__(self) -> None:
        if type(self.minimum_main_hits) is not int or not 0 <= self.minimum_main_hits <= 6:
            raise ValueError("minimum_main_hits must be an integer between 0 and 6")
        if type(self.require_special_hit) is not bool:
            raise ValueError("require_special_hit must be a boolean")
        _require_diagnostic_mode(self.expected_mode)

    @property
    def lottery(self) -> LotteryType:
        return LotteryType.BIG_LOTTO

    def canonical_dict(self) -> dict[str, object]:
        return {
            "criterion_type": type(self).__name__,
            "expected_mode": self.expected_mode.value,
            "lottery": self.lottery.value,
            "minimum_main_hits": self.minimum_main_hits,
            "require_special_hit": self.require_special_hit,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class PowerLottoSuccessCriterion:
    minimum_zone1_hits: int
    zone2_requirement: PowerLottoZone2Requirement
    expected_mode: MeasurementMode

    def __post_init__(self) -> None:
        if type(self.minimum_zone1_hits) is not int or not 0 <= self.minimum_zone1_hits <= 6:
            raise ValueError("minimum_zone1_hits must be an integer between 0 and 6")
        if type(self.zone2_requirement) is not PowerLottoZone2Requirement:
            raise ValueError("zone2_requirement must be a PowerLottoZone2Requirement")
        _require_diagnostic_mode(self.expected_mode)

    @property
    def lottery(self) -> LotteryType:
        return LotteryType.POWER_LOTTO

    def canonical_dict(self) -> dict[str, object]:
        return {
            "criterion_type": type(self).__name__,
            "expected_mode": self.expected_mode.value,
            "lottery": self.lottery.value,
            "minimum_zone1_hits": self.minimum_zone1_hits,
            "zone2_requirement": self.zone2_requirement.value,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class Daily539SuccessCriterion:
    minimum_main_hits: int
    expected_mode: MeasurementMode

    def __post_init__(self) -> None:
        if type(self.minimum_main_hits) is not int or not 0 <= self.minimum_main_hits <= 5:
            raise ValueError("minimum_main_hits must be an integer between 0 and 5")
        _require_diagnostic_mode(self.expected_mode)

    @property
    def lottery(self) -> LotteryType:
        return LotteryType.DAILY_539

    def canonical_dict(self) -> dict[str, object]:
        return {
            "criterion_type": type(self).__name__,
            "expected_mode": self.expected_mode.value,
            "lottery": self.lottery.value,
            "minimum_main_hits": self.minimum_main_hits,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_dict())


@dataclass(frozen=True, slots=True)
class OfficialTierSuccessCriterion:
    lottery: LotteryType
    official_prize_tier_id: str
    expected_mode: MeasurementMode = MeasurementMode.OFFICIAL_PRIZE_TIER

    def __post_init__(self) -> None:
        if type(self.lottery) is not LotteryType:
            raise ValueError("lottery must be a LotteryType")
        if (
            type(self.official_prize_tier_id) is not str
            or not self.official_prize_tier_id.strip()
        ):
            raise ValueError("official_prize_tier_id must be a non-empty string")
        if self.expected_mode is not MeasurementMode.OFFICIAL_PRIZE_TIER:
            raise ValueError("official-tier criteria require OFFICIAL_PRIZE_TIER mode")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "criterion_type": type(self).__name__,
            "expected_mode": self.expected_mode.value,
            "lottery": self.lottery.value,
            "official_prize_tier_id": self.official_prize_tier_id,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_dict())


SuccessCriterion = (
    BigLottoSuccessCriterion
    | PowerLottoSuccessCriterion
    | Daily539SuccessCriterion
    | OfficialTierSuccessCriterion
)


@dataclass(frozen=True, slots=True)
class WindowSuccessSummary:
    window_kind: WindowKind
    window_role: WindowRole
    requested_draw_count: int | None
    source_draw_count: int
    eligible_draw_count: int
    excluded_draw_count: int
    success_count: int
    failure_count: int
    success_rate: ExactSuccessRate
    first_target_draw: str
    last_target_draw: str
    nested_windows_independent: bool
    criterion_identity: str
    selection_identity: SelectionIdentity
    evaluation_status: WindowEvaluationStatus
    evidence_status: EvidenceStatus

    def __post_init__(self) -> None:
        if type(self.window_kind) is not WindowKind:
            raise ValueError("window_kind must be a WindowKind")
        if type(self.window_role) is not WindowRole:
            raise ValueError("window_role must be a WindowRole")
        if self.window_kind is WindowKind.FULL_HISTORY:
            if self.requested_draw_count is not None:
                raise ValueError("full history must use the full-history marker")
        elif type(self.requested_draw_count) is not int or self.requested_draw_count <= 0:
            raise ValueError("fixed windows require a positive requested draw count")
        for name in (
            "source_draw_count",
            "eligible_draw_count",
            "excluded_draw_count",
            "success_count",
            "failure_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.source_draw_count != self.eligible_draw_count + self.excluded_draw_count:
            raise ValueError("source draws must equal eligible plus excluded draws")
        if self.eligible_draw_count != self.success_count + self.failure_count:
            raise ValueError("eligible draws must equal successes plus failures")
        if type(self.success_rate) is not ExactSuccessRate:
            raise ValueError("success_rate must be an ExactSuccessRate")
        for name in ("first_target_draw", "last_target_draw", "criterion_identity"):
            value = getattr(self, name)
            if type(value) is not str or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if type(self.nested_windows_independent) is not bool:
            raise ValueError("nested_windows_independent must be a boolean")
        if type(self.selection_identity) is not SelectionIdentity:
            raise ValueError("selection_identity must be a SelectionIdentity")
        if type(self.evaluation_status) is not WindowEvaluationStatus:
            raise ValueError("evaluation_status must be a WindowEvaluationStatus")
        if self.evidence_status not in (EvidenceStatus.DESCRIPTIVE_ONLY, EvidenceStatus.NOT_READY):
            raise ValueError("window evidence must remain descriptive or not ready")

        if self.evaluation_status is WindowEvaluationStatus.COMPLETE:
            if self.eligible_draw_count == 0:
                raise ValueError("a complete window requires eligible draws")
            if self.success_rate != ExactSuccessRate(
                self.success_count, self.eligible_draw_count
            ):
                raise ValueError("complete-window rate must equal successes over eligible draws")
            if self.evidence_status is not EvidenceStatus.DESCRIPTIVE_ONLY:
                raise ValueError("complete windows remain DESCRIPTIVE_ONLY")
        else:
            if self.success_rate.is_available:
                raise ValueError("incomplete or unavailable windows require an unavailable rate")
            if self.evidence_status is not EvidenceStatus.NOT_READY:
                raise ValueError("incomplete or unavailable windows must be NOT_READY")

    def canonical_dict(self) -> dict[str, object]:
        return {
            "criterion_identity": self.criterion_identity,
            "eligible_draw_count": self.eligible_draw_count,
            "evaluation_status": self.evaluation_status.value,
            "evidence_status": self.evidence_status.value,
            "excluded_draw_count": self.excluded_draw_count,
            "failure_count": self.failure_count,
            "first_target_draw": self.first_target_draw,
            "last_target_draw": self.last_target_draw,
            "nested_windows_independent": self.nested_windows_independent,
            "requested_draw_count": self.requested_draw_count,
            "selection_identity": self.selection_identity.canonical_dict(),
            "source_draw_count": self.source_draw_count,
            "success_count": self.success_count,
            "success_rate": self.success_rate.canonical_dict(),
            "window_kind": self.window_kind.value,
            "window_role": self.window_role.value,
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_dict())


def _criterion_lottery(criterion: SuccessCriterion) -> LotteryType:
    return criterion.lottery


def _criterion_mode(criterion: SuccessCriterion) -> MeasurementMode:
    return criterion.expected_mode


def _criterion_identity(criterion: SuccessCriterion) -> str:
    return criterion.canonical_json()


def _is_criterion(value: object) -> TypeGuard[SuccessCriterion]:
    return type(value) in (
        BigLottoSuccessCriterion,
        PowerLottoSuccessCriterion,
        Daily539SuccessCriterion,
        OfficialTierSuccessCriterion,
    )


def evaluate_observation(
    observation: object,
    criterion: object,
) -> ObservationEvaluation:
    """Fail closed unless one well-typed observation matches one typed criterion."""

    if type(observation) is not StrategySuccessMeasurement or not _is_criterion(criterion):
        return ObservationEvaluation.EXCLUDED

    typed_criterion = criterion
    if (
        observation.selection.lottery is not _criterion_lottery(typed_criterion)
        or observation.mode is not _criterion_mode(typed_criterion)
    ):
        return ObservationEvaluation.EXCLUDED

    if type(typed_criterion) is OfficialTierSuccessCriterion:
        outcome = observation.outcome_signature
        if (
            type(outcome) is PowerLottoOutcomeSignature
            and outcome.eligibility is OutcomeEligibility.MISSING_PREDICTED_SECOND_ZONE
        ):
            return ObservationEvaluation.EXCLUDED
        if observation.official_prize_tier_id == typed_criterion.official_prize_tier_id:
            return ObservationEvaluation.SUCCESS
        return ObservationEvaluation.FAILURE

    if type(typed_criterion) is BigLottoSuccessCriterion:
        outcome = observation.outcome_signature
        if type(outcome) is not BigLottoOutcomeSignature:
            return ObservationEvaluation.EXCLUDED
        succeeded = outcome.main_hits >= typed_criterion.minimum_main_hits and (
            not typed_criterion.require_special_hit or outcome.special_hit
        )
    elif type(typed_criterion) is PowerLottoSuccessCriterion:
        outcome = observation.outcome_signature
        if type(outcome) is not PowerLottoOutcomeSignature:
            return ObservationEvaluation.EXCLUDED
        if (
            outcome.eligibility is OutcomeEligibility.MISSING_PREDICTED_SECOND_ZONE
            and typed_criterion.zone2_requirement is not PowerLottoZone2Requirement.NOT_USED
        ):
            return ObservationEvaluation.EXCLUDED
        zone2_matches = (
            typed_criterion.zone2_requirement is PowerLottoZone2Requirement.NOT_USED
            or (
                typed_criterion.zone2_requirement is PowerLottoZone2Requirement.HIT_REQUIRED
                and outcome.zone2_hit is True
            )
            or (
                typed_criterion.zone2_requirement is PowerLottoZone2Requirement.MISS_REQUIRED
                and outcome.zone2_hit is False
            )
        )
        succeeded = outcome.zone1_hits >= typed_criterion.minimum_zone1_hits and zone2_matches
    elif type(typed_criterion) is Daily539SuccessCriterion:
        outcome = observation.outcome_signature
        if type(outcome) is not Daily539OutcomeSignature:
            return ObservationEvaluation.EXCLUDED
        succeeded = outcome.main_hits >= typed_criterion.minimum_main_hits
    else:
        return ObservationEvaluation.EXCLUDED

    return ObservationEvaluation.SUCCESS if succeeded else ObservationEvaluation.FAILURE


def _validated_input(
    observations: tuple[StrategySuccessMeasurement, ...],
) -> tuple[StrategySuccessMeasurement, ...]:
    if type(observations) is not tuple or not observations:
        raise StrategySuccessEvaluationInputError(
            "observations must be a non-empty immutable tuple"
        )
    if any(type(observation) is not StrategySuccessMeasurement for observation in observations):
        raise StrategySuccessEvaluationInputError("observations contains a malformed measurement")

    first = observations[0]
    selection = first.selection
    lottery = selection.lottery
    mode = first.mode
    policy = first.window_policy
    policy_version = policy.policy_version
    target_draws: set[str] = set()

    for observation in observations:
        provenance = observation.provenance
        if provenance.target_draw is None:
            raise StrategySuccessEvaluationInputError("every observation requires target_draw")
        if provenance.history_cutoff is None:
            raise StrategySuccessEvaluationInputError("every observation requires history_cutoff")
        if provenance.window_policy_version is None:
            raise StrategySuccessEvaluationInputError(
                "every observation requires window_policy_version"
            )
        if provenance.target_draw in target_draws:
            raise StrategySuccessEvaluationInputError(
                f"duplicate target_draw: {provenance.target_draw}"
            )
        target_draws.add(provenance.target_draw)
        if observation.selection.lottery is not lottery:
            raise StrategySuccessEvaluationInputError("observations mix lotteries")
        if observation.mode is not mode:
            raise StrategySuccessEvaluationInputError("observations mix measurement modes")
        if observation.selection != selection:
            raise StrategySuccessEvaluationInputError("observations mix selection identities")
        if observation.window_policy.policy_version != policy_version:
            raise StrategySuccessEvaluationInputError("observations mix window-policy versions")
        if observation.window_policy != policy:
            raise StrategySuccessEvaluationInputError("observations mix window policies")

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


def evaluate_strategy_success_windows(
    observations: tuple[StrategySuccessMeasurement, ...],
    criterion: SuccessCriterion,
) -> tuple[WindowSuccessSummary, ...]:
    """Evaluate source order directly and return full/long/medium/short summaries."""

    source = _validated_input(observations)
    if not _is_criterion(criterion):
        raise StrategySuccessEvaluationInputError("criterion must be a typed success criterion")

    policy = source[0].window_policy
    selection = source[0].selection
    criterion_identity = _criterion_identity(criterion)
    summaries: list[WindowSuccessSummary] = []
    for kind, role, requested_count in _window_specs(policy):
        window = source if requested_count is None else source[-requested_count:]
        evaluations = tuple(evaluate_observation(item, criterion) for item in window)
        excluded = sum(
            1 for result in evaluations if result is ObservationEvaluation.EXCLUDED
        )
        successes = sum(
            1 for result in evaluations if result is ObservationEvaluation.SUCCESS
        )
        eligible = len(window) - excluded
        failures = eligible - successes

        if requested_count is not None and len(window) < requested_count:
            evaluation_status = WindowEvaluationStatus.INSUFFICIENT_DRAWS
        elif eligible == 0:
            evaluation_status = WindowEvaluationStatus.NO_ELIGIBLE_DRAWS
        else:
            evaluation_status = WindowEvaluationStatus.COMPLETE
        if evaluation_status is WindowEvaluationStatus.COMPLETE:
            rate = ExactSuccessRate(successes, eligible)
            evidence_status = EvidenceStatus.DESCRIPTIVE_ONLY
        else:
            rate = ExactSuccessRate.unavailable()
            evidence_status = EvidenceStatus.NOT_READY

        first_target = window[0].provenance.target_draw
        last_target = window[-1].provenance.target_draw
        if first_target is None or last_target is None:
            raise AssertionError("validated provenance lost target-draw identity")
        summaries.append(
            WindowSuccessSummary(
                window_kind=kind,
                window_role=role,
                requested_draw_count=requested_count,
                source_draw_count=len(window),
                eligible_draw_count=eligible,
                excluded_draw_count=excluded,
                success_count=successes,
                failure_count=failures,
                success_rate=rate,
                first_target_draw=first_target,
                last_target_draw=last_target,
                nested_windows_independent=policy.nested_windows_independent,
                criterion_identity=criterion_identity,
                selection_identity=selection,
                evaluation_status=evaluation_status,
                evidence_status=evidence_status,
            )
        )
    return tuple(summaries)


__all__ = [
    "BigLottoSuccessCriterion",
    "Daily539SuccessCriterion",
    "ExactSuccessRate",
    "ObservationEvaluation",
    "OfficialTierSuccessCriterion",
    "PowerLottoSuccessCriterion",
    "PowerLottoZone2Requirement",
    "StrategySuccessEvaluationInputError",
    "SuccessCriterion",
    "WindowEvaluationStatus",
    "WindowKind",
    "WindowSuccessSummary",
    "evaluate_observation",
    "evaluate_strategy_success_windows",
]
