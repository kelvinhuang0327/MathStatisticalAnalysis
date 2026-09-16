"""One-shot Stage C composition for runnable T539/P638 prediction seals.

This module deliberately supplies no scheduler, provider client, inferred target,
strategy cohort, or producer implementation.  A caller must provide an explicit
frozen cohort and producer authority; the composition then binds those values to
the canonical Stage A runnable-target gate and existing create-once seal store.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from lottolab.application.prospective_observer import repository_game_contracts
from lottolab.application.prospective_prediction_seal import (
    RunnablePredictionSealService,
    ScheduledPredictionProducerFactory,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import FrozenCohortRef, ProducerFingerprint
from lottolab.infrastructure.persistence.draw_schema import DATA_DIRECTORY_ENV
from lottolab.infrastructure.pre_outcome_target_operational import (
    PreOutcomeTargetOperationalComposition,
    compose_pre_outcome_target_operational_service,
)
from lottolab.infrastructure.prospective_observer_store import (
    FileSystemProspectiveObservationStore,
)

_SUPPORTED_LOTTERIES = frozenset(
    {LotteryType.DAILY_539, LotteryType.POWER_LOTTO}
)


@dataclass(frozen=True, slots=True)
class T539P638StageCComposition:
    """Resolved Stage A authority, durable seal store, and one-shot service."""

    target_authority: PreOutcomeTargetOperationalComposition
    prediction_store: FileSystemProspectiveObservationStore
    service: RunnablePredictionSealService


def compose_t539_p638_stage_c_prediction_seal(
    *,
    lottery_type: LotteryType,
    data_directory: Path,
    prediction_store_root: Path,
    producer_factory: ScheduledPredictionProducerFactory,
    cohort: FrozenCohortRef,
    base_producer_fingerprint: ProducerFingerprint,
    clock: Callable[[], datetime] | None = None,
) -> T539P638StageCComposition:
    """Compose Stage C without resolving a target or invoking a producer.

    ``service.seal_earliest()`` is the only execution boundary.  It first uses
    the Stage A ``find_earliest_unpopulated_future`` path and constructs the
    supplied producer only after the runnable and strict-time gates pass.
    """

    if type(lottery_type) is not LotteryType or lottery_type not in _SUPPORTED_LOTTERIES:
        raise ValueError("Stage C composition supports only DAILY_539 and POWER_LOTTO")
    selected_data_directory = _require_absolute_path(data_directory, "data_directory")
    selected_prediction_root = _require_absolute_path(
        prediction_store_root,
        "prediction_store_root",
    )
    if type(cohort) is not FrozenCohortRef or cohort.lottery_type is not lottery_type:
        raise ValueError("cohort must be an exact FrozenCohortRef for the configured lottery")
    if type(base_producer_fingerprint) is not ProducerFingerprint:
        raise ValueError("base_producer_fingerprint must be a ProducerFingerprint")

    selected_clock = _utc_now if clock is None else clock
    authority = compose_pre_outcome_target_operational_service(
        environ={DATA_DIRECTORY_ENV: str(selected_data_directory)},
        clock=selected_clock,
    )
    store = FileSystemProspectiveObservationStore(selected_prediction_root)
    contracts = repository_game_contracts()
    service = RunnablePredictionSealService(
        lottery_type=lottery_type,
        registration_service=authority.service,
        store=store,
        producer_factory=producer_factory,
        cohort=cohort,
        base_producer_fingerprint=base_producer_fingerprint,
        game_contracts={lottery_type: contracts[lottery_type]},
        clock=selected_clock,
    )
    return T539P638StageCComposition(
        target_authority=authority,
        prediction_store=store,
        service=service,
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_absolute_path(value: object, label: str) -> Path:
    if not isinstance(value, Path) or not value.is_absolute():
        raise ValueError(f"{label} must be an absolute Path")
    return value


__all__ = [
    "T539P638StageCComposition",
    "compose_t539_p638_stage_c_prediction_seal",
]
