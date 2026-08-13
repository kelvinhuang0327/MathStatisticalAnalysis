"""Deterministic runtime cycles for the generic prospective observer.

The prediction runner's dependency graph intentionally stops at an outcome-free
request source and :class:`PredictionPhaseService`.  Outcome-bearing requests
exist only on the separate scoring side.  Both runners execute sequentially in
one canonical order and let every technical or integrity exception propagate.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from lottolab.application.prospective_observer import (
    PredictionPhaseService,
    PredictionSyncStatus,
    ScorePhaseRequest,
    ScoreSyncStatus,
    ScoringPhaseService,
)
from lottolab.domain.prospective_observer import (
    PredictionAvailability,
    PredictionPhaseRequest,
    ProspectiveObservationIdentity,
)


class PredictionRequestSource(Protocol):
    """Load one deterministic, outcome-free set of Phase A requests."""

    def __call__(self) -> Iterable[PredictionPhaseRequest]: ...


class ScoreRequestSource(Protocol):
    """Load one deterministic set of Phase B requests and official outcomes."""

    def __call__(self) -> Iterable[ScorePhaseRequest]: ...


def _require_non_negative_integer(value: object, label: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a non-negative exact integer")


def _target_key(
    identity: ProspectiveObservationIdentity,
) -> tuple[str, str, str, date, int, str]:
    """Return the shared lottery/cohort/date/numeric-draw canonical key."""

    return (
        identity.lottery_type.value,
        identity.cohort_id,
        identity.cohort_version,
        identity.target_draw_date,
        int(identity.target_draw_number),
        identity.target_draw_number,
    )


def _validate_cycle_bounds(
    *,
    requested_targets: int,
    processed_targets: int,
    technical_failures: int,
    first_target: ProspectiveObservationIdentity | None,
    last_target: ProspectiveObservationIdentity | None,
) -> None:
    for label, value in (
        ("requested_targets", requested_targets),
        ("processed_targets", processed_targets),
        ("technical_failures", technical_failures),
    ):
        _require_non_negative_integer(value, label)
    if processed_targets + technical_failures != requested_targets:
        raise ValueError("processed targets plus technical failures must equal requested targets")
    if processed_targets == 0:
        if first_target is not None or last_target is not None:
            raise ValueError("an empty cycle must not carry first or last targets")
        return
    if (
        type(first_target) is not ProspectiveObservationIdentity
        or type(last_target) is not ProspectiveObservationIdentity
    ):
        raise ValueError("a processed cycle requires exact first and last target identities")
    if _target_key(first_target) > _target_key(last_target):
        raise ValueError("cycle target bounds must use canonical order")


@dataclass(frozen=True, slots=True)
class PredictionCycleSummary:
    """Immutable accounting for one successfully completed prediction cycle."""

    requested_targets: int
    processed_targets: int
    prediction_created: int
    prediction_idempotent: int
    prediction_unavailable: int
    technical_failures: int
    first_target: ProspectiveObservationIdentity | None
    last_target: ProspectiveObservationIdentity | None

    def __post_init__(self) -> None:
        _validate_cycle_bounds(
            requested_targets=self.requested_targets,
            processed_targets=self.processed_targets,
            technical_failures=self.technical_failures,
            first_target=self.first_target,
            last_target=self.last_target,
        )
        for label, value in (
            ("prediction_created", self.prediction_created),
            ("prediction_idempotent", self.prediction_idempotent),
            ("prediction_unavailable", self.prediction_unavailable),
        ):
            _require_non_negative_integer(value, label)
        if self.prediction_created + self.prediction_idempotent != self.processed_targets:
            raise ValueError("prediction status counts must equal processed targets")

    @property
    def prediction_exact_no_op(self) -> int:
        """Alias matching the underlying service status terminology."""

        return self.prediction_idempotent


@dataclass(frozen=True, slots=True)
class ScoreCycleSummary:
    """Immutable accounting for one successfully completed scoring cycle."""

    requested_targets: int
    processed_targets: int
    score_created: int
    score_idempotent: int
    outcome_unavailable: int
    technical_failures: int
    first_target: ProspectiveObservationIdentity | None
    last_target: ProspectiveObservationIdentity | None

    def __post_init__(self) -> None:
        _validate_cycle_bounds(
            requested_targets=self.requested_targets,
            processed_targets=self.processed_targets,
            technical_failures=self.technical_failures,
            first_target=self.first_target,
            last_target=self.last_target,
        )
        for label, value in (
            ("score_created", self.score_created),
            ("score_idempotent", self.score_idempotent),
            ("outcome_unavailable", self.outcome_unavailable),
        ):
            _require_non_negative_integer(value, label)
        if (
            self.score_created + self.score_idempotent + self.outcome_unavailable
            != self.processed_targets
        ):
            raise ValueError("score status counts must equal processed targets")

    @property
    def score_exact_no_op(self) -> int:
        """Alias matching the underlying service status terminology."""

        return self.score_idempotent

    @property
    def score_outcome_unavailable(self) -> int:
        return self.outcome_unavailable


@dataclass(frozen=True, slots=True)
class ProspectivePredictionRunner:
    """Run outcome-free Phase A requests sequentially in canonical order."""

    service: PredictionPhaseService
    request_source: PredictionRequestSource

    def run_cycle(self) -> PredictionCycleSummary:
        requests = tuple(self.request_source())
        for request in requests:
            if type(request) is not PredictionPhaseRequest:
                raise ValueError("prediction request source returned an invalid value")
        ordered = tuple(
            sorted(
                requests,
                key=lambda request: _target_key(
                    ProspectiveObservationIdentity.from_context(request.context)
                ),
            )
        )
        identities = tuple(
            ProspectiveObservationIdentity.from_context(request.context) for request in ordered
        )
        created = 0
        idempotent = 0
        unavailable = 0
        for request in ordered:
            result = self.service.sync(request)
            if result.status is PredictionSyncStatus.CREATED:
                created += 1
            elif result.status is PredictionSyncStatus.EXACT_IDEMPOTENT_NO_OP:
                idempotent += 1
            else:
                raise RuntimeError(f"unsupported prediction sync status: {result.status!r}")
            unavailable += sum(
                entry.availability is PredictionAvailability.UNAVAILABLE
                for entry in result.prediction.entries
            )
        return PredictionCycleSummary(
            requested_targets=len(ordered),
            processed_targets=len(ordered),
            prediction_created=created,
            prediction_idempotent=idempotent,
            prediction_unavailable=unavailable,
            technical_failures=0,
            first_target=identities[0] if identities else None,
            last_target=identities[-1] if identities else None,
        )


@dataclass(frozen=True, slots=True)
class ProspectiveScoreRunner:
    """Run Phase B requests without producing or repairing predictions."""

    service: ScoringPhaseService
    request_source: ScoreRequestSource

    def run_cycle(self) -> ScoreCycleSummary:
        requests = tuple(self.request_source())
        for request in requests:
            if type(request) is not ScorePhaseRequest:
                raise ValueError("score request source returned an invalid value")
        ordered = tuple(sorted(requests, key=lambda request: _target_key(request.identity)))
        identities = tuple(request.identity for request in ordered)
        created = 0
        idempotent = 0
        outcome_unavailable = 0
        for request in ordered:
            result = self.service.sync(request)
            if result.status is ScoreSyncStatus.CREATED:
                created += 1
            elif result.status is ScoreSyncStatus.EXACT_IDEMPOTENT_NO_OP:
                idempotent += 1
            elif result.status is ScoreSyncStatus.OUTCOME_UNAVAILABLE:
                outcome_unavailable += 1
            else:
                raise RuntimeError(f"unsupported score sync status: {result.status!r}")
        return ScoreCycleSummary(
            requested_targets=len(ordered),
            processed_targets=len(ordered),
            score_created=created,
            score_idempotent=idempotent,
            outcome_unavailable=outcome_unavailable,
            technical_failures=0,
            first_target=identities[0] if identities else None,
            last_target=identities[-1] if identities else None,
        )


def _validate_checkpoints(configured_checkpoints: tuple[int, ...]) -> None:
    if (
        type(configured_checkpoints) is not tuple
        or not configured_checkpoints
        or any(
            type(checkpoint) is not int or checkpoint <= 0
            for checkpoint in configured_checkpoints
        )
        or configured_checkpoints != tuple(sorted(set(configured_checkpoints)))
    ):
        raise ValueError("configured checkpoints must be strictly increasing positive integers")


def _checkpoint_projection(
    eligible_scored_count: int,
    configured_checkpoints: tuple[int, ...],
) -> tuple[tuple[int, ...], int | None, int | None, tuple[int, ...]]:
    reached = tuple(
        checkpoint for checkpoint in configured_checkpoints if checkpoint <= eligible_scored_count
    )
    remaining_checkpoints = tuple(
        checkpoint for checkpoint in configured_checkpoints if checkpoint > eligible_scored_count
    )
    next_checkpoint = remaining_checkpoints[0] if remaining_checkpoints else None
    remaining_to_next = (
        next_checkpoint - eligible_scored_count if next_checkpoint is not None else None
    )
    return reached, next_checkpoint, remaining_to_next, remaining_checkpoints


@dataclass(frozen=True, slots=True)
class CheckpointProgress:
    """Generic configured-checkpoint progress from a caller-owned eligible count."""

    eligible_scored_count: int
    configured_checkpoints: tuple[int, ...]
    reached_checkpoints: tuple[int, ...]
    next_checkpoint: int | None
    remaining_to_next_checkpoint: int | None
    remaining_checkpoints: tuple[int, ...]

    def __post_init__(self) -> None:
        _require_non_negative_integer(self.eligible_scored_count, "eligible_scored_count")
        _validate_checkpoints(self.configured_checkpoints)
        expected = _checkpoint_projection(
            self.eligible_scored_count,
            self.configured_checkpoints,
        )
        actual = (
            self.reached_checkpoints,
            self.next_checkpoint,
            self.remaining_to_next_checkpoint,
            self.remaining_checkpoints,
        )
        if actual != expected:
            raise ValueError("checkpoint progress does not match its configured inputs")

    @property
    def reached(self) -> tuple[int, ...]:
        return self.reached_checkpoints

    @property
    def remaining(self) -> int | None:
        return self.remaining_to_next_checkpoint


def project_checkpoint_progress(
    *,
    eligible_scored_count: int,
    configured_checkpoints: tuple[int, ...],
) -> CheckpointProgress:
    """Project generic progress without embedding any lottery protocol rules."""

    _require_non_negative_integer(eligible_scored_count, "eligible_scored_count")
    _validate_checkpoints(configured_checkpoints)
    reached, next_checkpoint, remaining_to_next, remaining_checkpoints = _checkpoint_projection(
        eligible_scored_count,
        configured_checkpoints,
    )
    return CheckpointProgress(
        eligible_scored_count=eligible_scored_count,
        configured_checkpoints=configured_checkpoints,
        reached_checkpoints=reached,
        next_checkpoint=next_checkpoint,
        remaining_to_next_checkpoint=remaining_to_next,
        remaining_checkpoints=remaining_checkpoints,
    )
