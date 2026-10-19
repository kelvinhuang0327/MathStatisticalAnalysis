"""Deterministic finite-candidate Study/Trial orchestration.

This module owns orchestration only.  It accepts an already-built temporal
holdout, already-immutable observations, and caller-supplied evaluation
callbacks.  Existing evaluators therefore remain the sole authority for
metric semantics, and the existing holdout model remains the sole authority
for split construction.

Discovery is deliberately one-way: every candidate sees only the discovery
tuple, winner selection reads only exact discovery objective values, and the
winner is frozen before the confirmation callback receives either it or the
confirmation tuple.  Full-history metadata is retained as descriptive output
but is never consulted by selection.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from fractions import Fraction
from itertools import pairwise
from types import MappingProxyType
from typing import Protocol, cast

from lottolab.application.candidate_success_matrix import ExactRational
from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessDrawIdentity,
    HistoricalPrefixTemporalHoldoutSplit,
)
from lottolab.evidence import canonical_json
from lottolab.research.base_method_evaluation import (
    BASE_METHOD_EVALUATOR_SEMANTIC_VERSION,
    MethodDrawObservation,
    MethodEvaluationRecord,
    WindowKind,
)

NATIVE_STUDY_SCHEMA_ID = "lottolab.research.native_study"
NATIVE_STUDY_SCHEMA_VERSION = "1.0.0"

_ASCII_DECIMAL = re.compile(r"[0-9]+", flags=re.ASCII)

type CanonicalValue = bool | int | str | tuple[CanonicalValue, ...] | Mapping[str, CanonicalValue]
type CanonicalPayload = bool | int | str | list[CanonicalPayload] | dict[str, CanonicalPayload]


def _empty_canonical_mapping() -> Mapping[str, CanonicalValue]:
    return {}


class NativeStudyError(ValueError):
    """Base class for fail-closed native Study/Trial errors."""


class NativeStudyContractError(NativeStudyError):
    """An immutable input or callback result violates the Study contract."""


class TrialPruned(Exception):
    """Signal a deterministic discovery-time pruning decision."""

    def __init__(self, reason: str) -> None:
        resolved = reason if type(reason) is str and reason else "trial pruned"
        self.reason = resolved
        super().__init__(resolved)


class NoCompletedTrialError(NativeStudyError):
    """No candidate completed discovery; confirmation was not exposed."""

    def __init__(self, trial_results: tuple[TrialResult, ...]) -> None:
        self.trial_results = trial_results
        super().__init__("no discovery trial completed; confirmation was not evaluated")


class ConfirmationEvaluationError(NativeStudyError):
    """The one authorized confirmation evaluation did not complete."""

    def __init__(self, winner: FrozenWinnerIdentity, cause: Exception) -> None:
        self.winner = winner
        self.cause_type = type(cause).__name__
        self.cause_message = str(cause) or self.cause_type
        super().__init__(
            f"confirmation evaluation failed for {winner.candidate_id}: "
            f"{self.cause_type}: {self.cause_message}"
        )


class TrialState(StrEnum):
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    PRUNED = "PRUNED"


class ObjectiveDirection(StrEnum):
    MAXIMIZE = "MAXIMIZE"
    MINIMIZE = "MINIMIZE"


class EvaluationValueField(StrEnum):
    """Exact ``MetricCell`` value selected by an evaluator-bound objective."""

    OBSERVED_VALUE = "OBSERVED_VALUE"
    RANDOM_REFERENCE = "RANDOM_REFERENCE"
    DELTA_VS_RANDOM = "DELTA_VS_RANDOM"


class ExactObjectiveValue(Fraction):
    """An immutable, arbitrary signed rational objective value."""

    __slots__ = ()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise NativeStudyContractError(message)


def _require_canonical_text(value: object, name: str) -> str:
    _require(
        type(value) is str and bool(value) and value == value.strip(),
        f"{name} must be a non-empty canonical string",
    )
    assert isinstance(value, str)
    return value


def _freeze_canonical_value(value: object, *, path: str) -> CanonicalValue:
    if type(value) is bool or type(value) is int or type(value) is str:
        assert isinstance(value, bool | int | str)
        return value
    if type(value) is tuple or type(value) is list:
        items = cast("tuple[object, ...] | list[object]", value)
        return tuple(
            _freeze_canonical_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(items)
        )
    if isinstance(value, Mapping):
        mapping = cast("Mapping[object, object]", value)
        keys = tuple(mapping.keys())
        _require(
            all(type(key) is str for key in keys),
            f"{path} mapping keys must be strings",
        )
        text_keys = tuple(cast("str", key) for key in keys)
        return MappingProxyType(
            {
                key: _freeze_canonical_value(mapping[key], path=f"{path}.{key}")
                for key in sorted(text_keys)
            }
        )
    raise NativeStudyContractError(
        f"{path} must contain only immutable LCJ-1 values; "
        f"got {type(value).__name__}"
    )


def _canonical_value(value: CanonicalValue) -> CanonicalPayload:
    if type(value) is bool or type(value) is int or type(value) is str:
        assert isinstance(value, bool | int | str)
        return value
    if type(value) is tuple:
        items = cast("tuple[CanonicalValue, ...]", value)
        return [_canonical_value(item) for item in items]
    if isinstance(value, Mapping):
        mapping = cast("Mapping[str, CanonicalValue]", value)
        return {key: _canonical_value(item) for key, item in mapping.items()}
    raise NativeStudyContractError(
        f"internal canonical value has unsupported type {type(value).__name__}"
    )


def _freeze_mapping(value: object, *, name: str) -> Mapping[str, CanonicalValue]:
    _require(isinstance(value, Mapping), f"{name} must be a mapping")
    frozen = _freeze_canonical_value(value, path=name)
    assert isinstance(frozen, Mapping)
    resolved = cast("Mapping[str, CanonicalValue]", frozen)
    payload = _canonical_value(resolved)
    canonical_json.validate_value_domain(payload)
    return resolved


def _canonical_mapping(value: Mapping[str, CanonicalValue]) -> dict[str, CanonicalPayload]:
    payload = _canonical_value(value)
    assert isinstance(payload, dict)
    canonical_json.validate_value_domain(payload)
    return payload


def _coerce_exact_value(value: object) -> ExactObjectiveValue:
    if type(value) is int:
        resolved = ExactObjectiveValue(value, 1)
    elif isinstance(value, Fraction | ExactRational):
        resolved = ExactObjectiveValue(value.numerator, value.denominator)
    else:
        raise NativeStudyContractError(
            "objective values must be Fraction, ExactRational, or integer; "
            "binary floats are forbidden"
        )
    canonical_json.validate_value_domain(
        {"denominator": resolved.denominator, "numerator": resolved.numerator}
    )
    return resolved


def _exact_value_dict(value: Fraction) -> dict[str, int]:
    return {"denominator": value.denominator, "numerator": value.numerator}


@dataclass(frozen=True, slots=True)
class ObjectiveSpec:
    """One lexicographically ordered exact objective.

    ``window_kind`` and ``metric_id`` optionally bind the objective to an
    existing ``MethodEvaluationRecord``.  ``FULL_HISTORY`` is rejected because
    that evaluator window is descriptive-only and may never select a winner.
    """

    objective_id: str
    direction: ObjectiveDirection
    window_kind: WindowKind | None = None
    metric_id: str | None = None
    value_field: EvaluationValueField = EvaluationValueField.OBSERVED_VALUE

    def __post_init__(self) -> None:
        _require_canonical_text(self.objective_id, "objective_id")
        _require(type(self.direction) is ObjectiveDirection, "direction is malformed")
        _require(type(self.value_field) is EvaluationValueField, "value_field is malformed")
        has_window = self.window_kind is not None
        has_metric = self.metric_id is not None
        _require(
            has_window == has_metric,
            "window_kind and metric_id must either both be supplied or both be omitted",
        )
        if has_window:
            _require(type(self.window_kind) is WindowKind, "window_kind is malformed")
            _require(
                self.window_kind is not WindowKind.FULL_HISTORY,
                "FULL_HISTORY is descriptive-only and cannot bind a selection objective",
            )
            _require_canonical_text(self.metric_id, "metric_id")

    @property
    def is_evaluator_bound(self) -> bool:
        return self.window_kind is not None

    def canonical_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "direction": self.direction.value,
            "objective_id": self.objective_id,
        }
        if self.window_kind is not None:
            assert self.metric_id is not None
            result["evaluation_binding"] = {
                "metric_id": self.metric_id,
                "value_field": self.value_field.value,
                "window_kind": self.window_kind.value,
            }
        return result


@dataclass(frozen=True, slots=True)
class TrialSpec:
    """One immutable candidate identity and its canonical parameters."""

    candidate_id: str
    parameters: Mapping[str, CanonicalValue] = field(default_factory=_empty_canonical_mapping)

    def __post_init__(self) -> None:
        _require_canonical_text(self.candidate_id, "candidate_id")
        object.__setattr__(
            self,
            "parameters",
            _freeze_mapping(self.parameters, name="parameters"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "parameters": _canonical_mapping(self.parameters),
        }


def _canonical_date(raw: str, *, name: str) -> date:
    try:
        parsed = date.fromisoformat(raw)
    except ValueError as exc:
        raise NativeStudyContractError(f"{name} must be an ISO calendar date") from exc
    _require(parsed.isoformat() == raw, f"{name} must use canonical YYYY-MM-DD form")
    return parsed


def _target_key(
    target: HistoricalPrefixSuccessDrawIdentity, *, name: str
) -> tuple[date, int]:
    _require(
        type(target) is HistoricalPrefixSuccessDrawIdentity,
        f"{name} is malformed",
    )
    return (_canonical_date(target.draw_date, name=f"{name}.draw_date"), target.draw_number)


def _validate_split_shape(split: HistoricalPrefixTemporalHoldoutSplit) -> None:
    _require(
        type(split) is HistoricalPrefixTemporalHoldoutSplit,
        "temporal_holdout_split is malformed",
    )
    _require_canonical_text(split.split_method, "split_method")
    for field_name in (
        "total_assignment_count",
        "warmup_count",
        "discovery_count",
        "confirmation_count",
    ):
        value = getattr(split, field_name)
        _require(
            type(value) is int and value >= 0,
            f"{field_name} must be a non-negative integer",
        )
    _require(split.discovery_count > 0, "discovery_count must be positive")
    _require(split.confirmation_count > 0, "confirmation_count must be positive")
    _require(
        split.total_assignment_count
        == split.warmup_count + split.discovery_count + split.confirmation_count,
        "temporal holdout counts are inconsistent",
    )

    discovery_first_target = split.discovery_first_target
    discovery_last_target = split.discovery_last_target
    confirmation_first_target = split.confirmation_first_target
    confirmation_last_target = split.confirmation_last_target
    endpoints = (
        discovery_first_target,
        discovery_last_target,
        confirmation_first_target,
        confirmation_last_target,
    )
    _require(all(item is not None for item in endpoints), "complete split endpoints are required")
    assert discovery_first_target is not None
    assert discovery_last_target is not None
    assert confirmation_first_target is not None
    assert confirmation_last_target is not None
    discovery_first = _target_key(discovery_first_target, name="discovery_first_target")
    discovery_last = _target_key(discovery_last_target, name="discovery_last_target")
    confirmation_first = _target_key(confirmation_first_target, name="confirmation_first_target")
    confirmation_last = _target_key(confirmation_last_target, name="confirmation_last_target")
    if split.discovery_count == 1:
        _require(discovery_first == discovery_last, "single discovery identity is inconsistent")
    else:
        _require(discovery_first < discovery_last, "discovery split is reversed")
    if split.confirmation_count == 1:
        _require(
            confirmation_first == confirmation_last,
            "single confirmation identity is inconsistent",
        )
    else:
        _require(confirmation_first < confirmation_last, "confirmation split is reversed")
    _require(
        discovery_last < confirmation_first,
        "discovery and confirmation identities overlap or are reversed",
    )
    canonical_json.validate_value_domain(_split_dict(split))


def _target_dict(target: HistoricalPrefixSuccessDrawIdentity | None) -> dict[str, object]:
    _require(target is not None, "complete split endpoint is missing")
    assert target is not None
    return {
        "draw_date": target.draw_date,
        "draw_number": target.draw_number,
        "draw_sha256": target.draw_sha256,
    }


def _split_dict(split: HistoricalPrefixTemporalHoldoutSplit) -> dict[str, object]:
    return {
        "confirmation_count": split.confirmation_count,
        "confirmation_first_target": _target_dict(split.confirmation_first_target),
        "confirmation_last_target": _target_dict(split.confirmation_last_target),
        "discovery_count": split.discovery_count,
        "discovery_first_target": _target_dict(split.discovery_first_target),
        "discovery_last_target": _target_dict(split.discovery_last_target),
        "split_method": split.split_method,
        "total_assignment_count": split.total_assignment_count,
        "warmup_count": split.warmup_count,
    }


@dataclass(frozen=True, slots=True)
class StudySpec:
    """Immutable finite candidate set, objective order, and holdout identity."""

    study_id: str
    objectives: tuple[ObjectiveSpec, ...]
    trials: tuple[TrialSpec, ...]
    temporal_holdout_split: HistoricalPrefixTemporalHoldoutSplit
    full_history_metadata: Mapping[str, CanonicalValue] = field(
        default_factory=_empty_canonical_mapping
    )

    def __post_init__(self) -> None:
        _require_canonical_text(self.study_id, "study_id")
        _require(
            type(self.objectives) is tuple and len(self.objectives) > 0,
            "objectives must be a non-empty immutable tuple",
        )
        _require(
            all(type(item) is ObjectiveSpec for item in self.objectives),
            "objectives contains a malformed item",
        )
        objective_ids = tuple(item.objective_id for item in self.objectives)
        _require(
            len(objective_ids) == len(set(objective_ids)),
            "objective_id values must be unique",
        )
        _require(
            type(self.trials) is tuple and len(self.trials) > 0,
            "trials must be a non-empty immutable tuple",
        )
        _require(
            all(type(item) is TrialSpec for item in self.trials),
            "trials contains a malformed item",
        )
        candidate_ids = tuple(item.candidate_id for item in self.trials)
        _require(
            len(candidate_ids) == len(set(candidate_ids)),
            "candidate_id values must be unique",
        )
        _require(
            candidate_ids == tuple(sorted(candidate_ids)),
            "trials must use canonical ascending candidate_id order",
        )
        _validate_split_shape(self.temporal_holdout_split)
        object.__setattr__(
            self,
            "full_history_metadata",
            _freeze_mapping(self.full_history_metadata, name="full_history_metadata"),
        )

    @property
    def candidates(self) -> tuple[TrialSpec, ...]:
        return self.trials

    def canonical_dict(self) -> dict[str, object]:
        return {
            "full_history_metadata": _canonical_mapping(self.full_history_metadata),
            "objectives": [item.canonical_dict() for item in self.objectives],
            "study_id": self.study_id,
            "temporal_holdout_split": _split_dict(self.temporal_holdout_split),
            "trials": [item.canonical_dict() for item in self.trials],
        }


@dataclass(frozen=True, slots=True)
class TrialEvaluation:
    """Exact discovery/confirmation values returned by a native callback."""

    objective_values: tuple[ExactObjectiveValue, ...]
    full_history_metadata: Mapping[str, CanonicalValue] = field(
        default_factory=_empty_canonical_mapping
    )

    def __post_init__(self) -> None:
        _require(type(self.objective_values) is tuple, "objective_values must be a tuple")
        object.__setattr__(
            self,
            "objective_values",
            tuple(_coerce_exact_value(item) for item in self.objective_values),
        )
        object.__setattr__(
            self,
            "full_history_metadata",
            _freeze_mapping(self.full_history_metadata, name="full_history_metadata"),
        )


@dataclass(frozen=True, slots=True)
class TrialResult:
    trial: TrialSpec
    state: TrialState
    objective_values: tuple[ExactObjectiveValue, ...] = ()
    full_history_metadata: Mapping[str, CanonicalValue] = field(
        default_factory=_empty_canonical_mapping
    )
    failure_type: str = ""
    detail: str = ""

    def __post_init__(self) -> None:
        _require(type(self.trial) is TrialSpec, "trial is malformed")
        _require(type(self.state) is TrialState, "state is malformed")
        _require(type(self.objective_values) is tuple, "objective_values must be a tuple")
        object.__setattr__(
            self,
            "objective_values",
            tuple(_coerce_exact_value(item) for item in self.objective_values),
        )
        object.__setattr__(
            self,
            "full_history_metadata",
            _freeze_mapping(self.full_history_metadata, name="full_history_metadata"),
        )
        if self.state is TrialState.COMPLETE:
            _require(bool(self.objective_values), "a completed trial requires objective values")
            _require(
                self.failure_type == "" and self.detail == "",
                "a completed trial cannot carry failure details",
            )
        else:
            _require(not self.objective_values, "an incomplete trial cannot carry objective values")
            _require(self.failure_type != "", "an incomplete trial requires failure_type")
            _require(self.detail != "", "an incomplete trial requires detail")

    @property
    def candidate_id(self) -> str:
        return self.trial.candidate_id

    def canonical_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "candidate_id": self.candidate_id,
            "full_history_metadata": _canonical_mapping(self.full_history_metadata),
            "objective_values": [
                _exact_value_dict(item) for item in self.objective_values
            ],
            "parameters": _canonical_mapping(self.trial.parameters),
            "state": self.state.value,
        }
        if self.state is not TrialState.COMPLETE:
            result["detail"] = self.detail
            result["failure_type"] = self.failure_type
        return result


@dataclass(frozen=True, slots=True)
class FrozenWinnerIdentity:
    """Winner and parameters fixed entirely from completed discovery trials."""

    trial: TrialSpec
    discovery_objective_values: tuple[ExactObjectiveValue, ...]

    def __post_init__(self) -> None:
        _require(type(self.trial) is TrialSpec, "winner trial is malformed")
        _require(
            type(self.discovery_objective_values) is tuple
            and len(self.discovery_objective_values) > 0,
            "winner requires discovery objective values",
        )
        object.__setattr__(
            self,
            "discovery_objective_values",
            tuple(_coerce_exact_value(item) for item in self.discovery_objective_values),
        )

    @property
    def candidate_id(self) -> str:
        return self.trial.candidate_id

    @property
    def parameters(self) -> Mapping[str, CanonicalValue]:
        return self.trial.parameters

    def canonical_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "discovery_objective_values": [
                _exact_value_dict(item) for item in self.discovery_objective_values
            ],
            "parameters": _canonical_mapping(self.parameters),
        }


@dataclass(frozen=True, slots=True)
class ConfirmationResult:
    winner: FrozenWinnerIdentity
    objective_values: tuple[ExactObjectiveValue, ...]
    full_history_metadata: Mapping[str, CanonicalValue] = field(
        default_factory=_empty_canonical_mapping
    )

    def __post_init__(self) -> None:
        _require(type(self.winner) is FrozenWinnerIdentity, "confirmation winner is malformed")
        _require(
            type(self.objective_values) is tuple and len(self.objective_values) > 0,
            "confirmation requires objective values",
        )
        object.__setattr__(
            self,
            "objective_values",
            tuple(_coerce_exact_value(item) for item in self.objective_values),
        )
        object.__setattr__(
            self,
            "full_history_metadata",
            _freeze_mapping(self.full_history_metadata, name="full_history_metadata"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "full_history_metadata": _canonical_mapping(self.full_history_metadata),
            "objective_values": [
                _exact_value_dict(item) for item in self.objective_values
            ],
            "winner": self.winner.canonical_dict(),
        }


@dataclass(frozen=True, slots=True)
class StudyResult:
    spec: StudySpec
    trials: tuple[TrialResult, ...]
    winner: FrozenWinnerIdentity
    confirmation: ConfirmationResult

    def __post_init__(self) -> None:
        _require(type(self.spec) is StudySpec, "spec is malformed")
        _require(type(self.trials) is tuple, "trials must be a tuple")
        _require(
            tuple(item.trial for item in self.trials) == self.spec.trials,
            "trial results must retain canonical candidate order",
        )
        completed = tuple(item for item in self.trials if item.state is TrialState.COMPLETE)
        _require(bool(completed), "study result requires a completed discovery trial")
        winner_result = next(
            (item for item in completed if item.candidate_id == self.winner.candidate_id),
            None,
        )
        _require(winner_result is not None, "winner is not a completed discovery trial")
        assert winner_result is not None
        _require(
            winner_result.trial == self.winner.trial
            and winner_result.objective_values == self.winner.discovery_objective_values,
            "winner identity does not match its frozen discovery result",
        )
        _require(
            self.confirmation.winner == self.winner,
            "confirmation must bind the already-frozen winner",
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "confirmation": self.confirmation.canonical_dict(),
            "schema_id": NATIVE_STUDY_SCHEMA_ID,
            "schema_version": NATIVE_STUDY_SCHEMA_VERSION,
            "spec": self.spec.canonical_dict(),
            "trials": [item.canonical_dict() for item in self.trials],
            "winner": self.winner.canonical_dict(),
        }

    def canonical_json(self) -> str:
        return canonical_json.canonical_bytes(self.canonical_dict()).decode("utf-8")

    def canonical_sha256(self) -> str:
        return canonical_json.sha256_hex(canonical_json.canonical_bytes(self.canonical_dict()))

    @property
    def sha256(self) -> str:
        return self.canonical_sha256()


class DiscoveryEvaluator(Protocol):
    def __call__(
        self,
        trial: TrialSpec,
        observations: tuple[MethodDrawObservation, ...],
        /,
    ) -> object: ...


class ConfirmationEvaluator(Protocol):
    def __call__(
        self,
        winner: FrozenWinnerIdentity,
        observations: tuple[MethodDrawObservation, ...],
        /,
    ) -> object: ...


def _observation_key(
    observation: MethodDrawObservation, *, name: str
) -> tuple[date, int]:
    _require(type(observation) is MethodDrawObservation, f"{name} is malformed")
    _require(
        _ASCII_DECIMAL.fullmatch(observation.draw_id) is not None,
        f"{name}.draw_id must be an ASCII decimal identity",
    )
    return (
        _canonical_date(observation.draw_date, name=f"{name}.draw_date"),
        int(observation.draw_id),
    )


def _validate_partition_observations(
    spec: StudySpec,
    discovery: tuple[MethodDrawObservation, ...],
    confirmation: tuple[MethodDrawObservation, ...],
) -> None:
    _require(type(discovery) is tuple, "discovery observations must be a tuple")
    _require(type(confirmation) is tuple, "confirmation observations must be a tuple")
    split = spec.temporal_holdout_split
    _require(
        len(discovery) == split.discovery_count,
        "discovery observation count contradicts temporal_holdout_split",
    )
    _require(
        len(confirmation) == split.confirmation_count,
        "confirmation observation count contradicts temporal_holdout_split",
    )

    discovery_keys = tuple(
        _observation_key(item, name=f"discovery[{index}]")
        for index, item in enumerate(discovery)
    )
    confirmation_keys = tuple(
        _observation_key(item, name=f"confirmation[{index}]")
        for index, item in enumerate(confirmation)
    )
    _require(
        all(left < right for left, right in pairwise(discovery_keys)),
        "discovery observations are duplicated or non-chronological",
    )
    _require(
        all(left < right for left, right in pairwise(confirmation_keys)),
        "confirmation observations are duplicated or non-chronological",
    )
    discovery_draws = {key[1] for key in discovery_keys}
    confirmation_draws = {key[1] for key in confirmation_keys}
    _require(
        len(discovery_draws) == len(discovery_keys),
        "discovery contains duplicated partition identity",
    )
    _require(
        len(confirmation_draws) == len(confirmation_keys),
        "confirmation contains duplicated partition identity",
    )
    _require(
        discovery_draws.isdisjoint(confirmation_draws),
        "discovery and confirmation partition identities overlap",
    )
    _require(
        discovery_keys[-1] < confirmation_keys[0],
        "discovery and confirmation partitions are reversed or non-chronological",
    )

    endpoint_pairs = (
        (split.discovery_first_target, discovery[0], "discovery_first_target"),
        (split.discovery_last_target, discovery[-1], "discovery_last_target"),
        (split.confirmation_first_target, confirmation[0], "confirmation_first_target"),
        (split.confirmation_last_target, confirmation[-1], "confirmation_last_target"),
    )
    for target, observation, name in endpoint_pairs:
        _require(target is not None, f"{name} is missing")
        assert target is not None
        _require(
            target.draw_number == int(observation.draw_id)
            and target.draw_date == observation.draw_date,
            f"{name} contradicts the supplied observation partition",
        )


def _metric_value(record: MethodEvaluationRecord, objective: ObjectiveSpec) -> Fraction:
    _require(
        objective.window_kind is not None and objective.metric_id is not None,
        f"objective {objective.objective_id!r} is not bound to MethodEvaluationRecord",
    )
    window_kind = objective.window_kind
    metric_id = objective.metric_id
    assert window_kind is not None
    assert metric_id is not None
    block = record.windows.get(window_kind)
    _require(block is not None, f"evaluation is missing {window_kind.value}")
    assert block is not None
    cell = block.metrics.get(metric_id)
    _require(cell is not None, f"evaluation is missing metric {metric_id!r}")
    assert cell is not None
    if objective.value_field is EvaluationValueField.OBSERVED_VALUE:
        value = cell.observed_value
    elif objective.value_field is EvaluationValueField.RANDOM_REFERENCE:
        value = cell.random_reference
    else:
        value = cell.delta_vs_random
    _require(
        value is not None,
        f"evaluation value for objective {objective.objective_id!r} is unavailable",
    )
    assert value is not None
    return value


def _full_history_metadata(record: MethodEvaluationRecord) -> Mapping[str, CanonicalValue]:
    block = record.windows[WindowKind.FULL_HISTORY]
    metric_rows: list[dict[str, CanonicalValue]] = []
    for metric_id in sorted(block.metrics):
        cell = block.metrics[metric_id]
        row: dict[str, CanonicalValue] = {
            "baseline_method": cell.baseline_method.value,
            "eligible_draw_count": cell.eligible_draw_count,
            "evaluable_status": cell.evaluable_status.value,
            "metric_id": metric_id,
            "random_status": cell.random_status.value,
        }
        if cell.success_draw_count is not None:
            row["success_draw_count"] = cell.success_draw_count
        if cell.observed_value is not None:
            row["observed_value"] = _exact_value_dict(cell.observed_value)
        if cell.random_reference is not None:
            row["random_reference"] = _exact_value_dict(cell.random_reference)
        if cell.delta_vs_random is not None:
            row["delta_vs_random"] = _exact_value_dict(cell.delta_vs_random)
        metric_rows.append(row)
    return _freeze_mapping(
        {
            "eligible_draw_count": block.eligible_draw_count,
            "evaluator_semantic_version": BASE_METHOD_EVALUATOR_SEMANTIC_VERSION,
            "method_family": record.identity.method_family,
            "method_id": record.identity.method_id,
            "method_version": record.identity.method_version,
            "metrics": tuple(metric_rows),
            "window_role": block.window_role.value,
            "window_status": block.window_status.value,
        },
        name="full_history_metadata",
    )


def _normalize_evaluation(spec: StudySpec, raw: object) -> TrialEvaluation:
    if type(raw) is TrialEvaluation:
        evaluation = raw
    elif type(raw) is MethodEvaluationRecord:
        evaluation = TrialEvaluation(
            objective_values=tuple(
                _coerce_exact_value(_metric_value(raw, item)) for item in spec.objectives
            ),
            full_history_metadata=_full_history_metadata(raw),
        )
    elif type(raw) is tuple:
        raw_values = cast("tuple[object, ...]", raw)
        evaluation = TrialEvaluation(
            objective_values=tuple(_coerce_exact_value(item) for item in raw_values)
        )
    else:
        raise NativeStudyContractError(
            "evaluation callback must return TrialEvaluation, MethodEvaluationRecord, "
            "or an immutable tuple of exact values"
        )
    _require(
        len(evaluation.objective_values) == len(spec.objectives),
        "evaluation objective count contradicts StudySpec objective order",
    )
    return evaluation


def _failed_trial(trial: TrialSpec, state: TrialState, exc: Exception) -> TrialResult:
    detail = str(exc) or type(exc).__name__
    return TrialResult(
        trial=trial,
        state=state,
        failure_type=type(exc).__name__,
        detail=detail,
    )


def _candidate_precedes(
    candidate: TrialResult,
    incumbent: TrialResult,
    objectives: tuple[ObjectiveSpec, ...],
) -> bool:
    for index, objective in enumerate(objectives):
        candidate_value = candidate.objective_values[index]
        incumbent_value = incumbent.objective_values[index]
        if candidate_value == incumbent_value:
            continue
        if objective.direction is ObjectiveDirection.MAXIMIZE:
            return candidate_value > incumbent_value
        return candidate_value < incumbent_value
    return candidate.candidate_id < incumbent.candidate_id


def _select_winner(
    completed: tuple[TrialResult, ...], objectives: tuple[ObjectiveSpec, ...]
) -> TrialResult:
    winner = completed[0]
    for candidate in completed[1:]:
        if _candidate_precedes(candidate, winner, objectives):
            winner = candidate
    return winner


def run_study(
    spec: StudySpec,
    *,
    discovery_observations: tuple[MethodDrawObservation, ...],
    confirmation_observations: tuple[MethodDrawObservation, ...],
    evaluate_discovery: DiscoveryEvaluator,
    evaluate_confirmation: ConfirmationEvaluator,
) -> StudyResult:
    """Run every discovery trial, freeze one winner, then confirm it once.

    Candidate order and partition identity are validated before any callback.
    Discovery callbacks never receive confirmation observations or descriptive
    study metadata.  Confirmation is unreachable until every discovery result
    has been retained and a completed-trial winner has been frozen.
    """

    _require(type(spec) is StudySpec, "spec is malformed")
    _validate_partition_observations(
        spec,
        discovery_observations,
        confirmation_observations,
    )

    trial_results: list[TrialResult] = []
    for trial in spec.trials:
        try:
            evaluation = _normalize_evaluation(
                spec,
                evaluate_discovery(trial, discovery_observations),
            )
        except TrialPruned as exc:
            trial_results.append(_failed_trial(trial, TrialState.PRUNED, exc))
        except Exception as exc:
            trial_results.append(_failed_trial(trial, TrialState.FAILED, exc))
        else:
            trial_results.append(
                TrialResult(
                    trial=trial,
                    state=TrialState.COMPLETE,
                    objective_values=evaluation.objective_values,
                    full_history_metadata=evaluation.full_history_metadata,
                )
            )

    retained = tuple(trial_results)
    completed = tuple(item for item in retained if item.state is TrialState.COMPLETE)
    if not completed:
        raise NoCompletedTrialError(retained)

    selected = _select_winner(completed, spec.objectives)
    frozen_winner = FrozenWinnerIdentity(
        trial=selected.trial,
        discovery_objective_values=selected.objective_values,
    )

    try:
        confirmation_evaluation = _normalize_evaluation(
            spec,
            evaluate_confirmation(frozen_winner, confirmation_observations),
        )
    except Exception as exc:
        raise ConfirmationEvaluationError(frozen_winner, exc) from exc

    confirmation = ConfirmationResult(
        winner=frozen_winner,
        objective_values=confirmation_evaluation.objective_values,
        full_history_metadata=confirmation_evaluation.full_history_metadata,
    )
    return StudyResult(
        spec=spec,
        trials=retained,
        winner=frozen_winner,
        confirmation=confirmation,
    )


run_native_study = run_study


__all__ = [
    "NATIVE_STUDY_SCHEMA_ID",
    "NATIVE_STUDY_SCHEMA_VERSION",
    "CanonicalValue",
    "ConfirmationEvaluationError",
    "ConfirmationEvaluator",
    "ConfirmationResult",
    "DiscoveryEvaluator",
    "EvaluationValueField",
    "ExactObjectiveValue",
    "FrozenWinnerIdentity",
    "NativeStudyContractError",
    "NativeStudyError",
    "NoCompletedTrialError",
    "ObjectiveDirection",
    "ObjectiveSpec",
    "StudyResult",
    "StudySpec",
    "TrialEvaluation",
    "TrialPruned",
    "TrialResult",
    "TrialSpec",
    "TrialState",
    "run_native_study",
    "run_study",
]
