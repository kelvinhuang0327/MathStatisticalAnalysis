"""Read-only Next-Draw Recommendation target/seal lifecycle lookup.

Reports the externally observable lifecycle for one lottery type --
``WAITING_FOR_ELIGIBLE_TARGET``, ``TARGET_AVAILABLE``, ``PREDICTIONS_SEALED``,
or ``OUTCOME_AVAILABLE`` -- without ever creating, registering, or sealing
anything. Every collaborator this use case calls is itself read-only: the
future-draw-identity reader, the causal-history-free outcome presence probe,
and the seal store's ``get_seal`` lookup. Calling ``execute`` twice in a row
must be indistinguishable from calling it once.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from lottolab.application.ports import FutureDrawIdentityReader
from lottolab.application.pre_outcome_target import OutcomePresenceProbe
from lottolab.application.pre_outcome_target_operational import (
    OutcomePresenceEvidenceUnavailableError,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.next_draw_recommendation_seal import (
    NextDrawRecommendationLifecycleState,
    NextDrawRecommendationSeal,
)
from lottolab.domain.prospective_observer import ObservationTarget, OutcomePresenceAtPrediction


@runtime_checkable
class NextDrawRecommendationSealReader(Protocol):
    """Read-only half of ``NextDrawRecommendationSealStore``."""

    def get_seal(self, target: ObservationTarget) -> NextDrawRecommendationSeal | None: ...


@dataclass(frozen=True, slots=True)
class NextDrawRecommendationLifecycleView:
    """One point-in-time, side-effect-free lifecycle snapshot."""

    state: NextDrawRecommendationLifecycleState
    target: ObservationTarget | None
    seal: NextDrawRecommendationSeal | None

    def __post_init__(self) -> None:
        if type(self.state) is not NextDrawRecommendationLifecycleState:
            raise ValueError("state must be a NextDrawRecommendationLifecycleState")
        has_target = self.target is not None
        expects_target = (
            self.state is not NextDrawRecommendationLifecycleState.WAITING_FOR_ELIGIBLE_TARGET
        )
        if has_target != expects_target:
            raise ValueError("target must be present exactly when the state names one")
        has_seal = self.seal is not None
        expects_seal = self.state in {
            NextDrawRecommendationLifecycleState.PREDICTIONS_SEALED,
            NextDrawRecommendationLifecycleState.OUTCOME_AVAILABLE,
        }
        if has_seal != expects_seal:
            raise ValueError("seal must be present exactly when the state is sealed or later")
        if self.seal is not None and self.target is not None and self.seal.target != self.target:
            raise ValueError("a sealed view's seal must be bound to the reported target")


class GetNextDrawRecommendationLifecycle:
    """Resolve the current lifecycle state for one lottery type, read-only."""

    def __init__(
        self,
        *,
        future_draw_identity_reader: FutureDrawIdentityReader,
        outcome_presence_probe: OutcomePresenceProbe,
        seal_reader: NextDrawRecommendationSealReader,
        clock: Callable[[], datetime],
    ) -> None:
        self._future_draw_identity_reader = future_draw_identity_reader
        self._outcome_presence_probe = outcome_presence_probe
        self._seal_reader = seal_reader
        self._clock = clock

    def execute(self, lottery_type: LotteryType) -> NextDrawRecommendationLifecycleView:
        now = self._clock()
        future_record = self._future_draw_identity_reader.find_earliest_unpopulated_future(
            lottery_type, now
        )
        due_record = self._future_draw_identity_reader.find_earliest_unpopulated_due(
            lottery_type, now
        )
        candidate = future_record if future_record is not None else due_record
        if candidate is None:
            return NextDrawRecommendationLifecycleView(
                state=NextDrawRecommendationLifecycleState.WAITING_FOR_ELIGIBLE_TARGET,
                target=None,
                seal=None,
            )

        target = candidate.announcement.target
        seal = self._seal_reader.get_seal(target)
        if seal is None:
            if future_record is None:
                # The only unpopulated candidate is already due (its pre-draw
                # sealing window has closed) and nothing sealed it in time:
                # there is currently no *eligible* (still sealable) target.
                return NextDrawRecommendationLifecycleView(
                    state=NextDrawRecommendationLifecycleState.WAITING_FOR_ELIGIBLE_TARGET,
                    target=None,
                    seal=None,
                )
            return NextDrawRecommendationLifecycleView(
                state=NextDrawRecommendationLifecycleState.TARGET_AVAILABLE,
                target=target,
                seal=None,
            )

        outcome_available = _probe_outcome_available(self._outcome_presence_probe, target, now)
        state = (
            NextDrawRecommendationLifecycleState.OUTCOME_AVAILABLE
            if outcome_available
            else NextDrawRecommendationLifecycleState.PREDICTIONS_SEALED
        )
        return NextDrawRecommendationLifecycleView(state=state, target=target, seal=seal)


def _probe_outcome_available(
    probe: OutcomePresenceProbe, target: ObservationTarget, as_of: datetime
) -> bool:
    try:
        attestation = probe.probe(target, as_of=as_of)
    except OutcomePresenceEvidenceUnavailableError:
        # No official-provider audit confirms either presence or absence yet;
        # this is a read-only lookup, so stay at the last confirmed state
        # (sealed) rather than fail the request or claim an outcome exists.
        return False
    return attestation.presence is OutcomePresenceAtPrediction.PRESENT


__all__ = [
    "GetNextDrawRecommendationLifecycle",
    "NextDrawRecommendationLifecycleView",
    "NextDrawRecommendationSealReader",
    "OutcomePresenceEvidenceUnavailableError",
]
