"""Composition adapter for T539 and P638 recurring automation runner.

Binds the canonical SQLite draw repository, future draw identity reader,
prospective observation store, forward evidence ledger store, and game-specific
Stage C / E / G services into a unified Stage H recurring automation service.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from lottolab.application.forward_evidence_ledger import (
    ForwardEvidenceLedgerService,
)
from lottolab.application.prospective_observer import (
    ScoringPhaseService,
    repository_game_contracts,
)
from lottolab.application.prospective_prediction_seal import (
    RunnablePredictionSealService,
    ScheduledPredictionProducerFactory,
)
from lottolab.application.prospective_result_join import (
    ProspectiveResultJoinService,
)
from lottolab.application.t539_p638_recurring_automation import (
    SingleGameRecurringRunner,
    T539P638RecurringAutomationService,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.prospective_observer import (
    FrozenCohortRef,
    ProducerFingerprint,
)
from lottolab.infrastructure.forward_evidence_ledger_store import (
    FileSystemForwardEvidenceLedgerStore,
)
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.future_draw_identity_repository import (
    SQLiteFutureDrawIdentityReader,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawRepository
from lottolab.infrastructure.pre_outcome_target_operational import (
    compose_pre_outcome_target_operational_service,
)
from lottolab.infrastructure.prospective_observer_store import (
    FileSystemProspectiveObservationStore,
)

_SUPPORTED_LOTTERIES = frozenset({LotteryType.DAILY_539, LotteryType.POWER_LOTTO})


@dataclass(frozen=True, slots=True)
class SingleGameRecurringComposition:
    """Resolved composition for a single game's recurring automation runner."""

    lottery_type: LotteryType
    data_paths: LocalDataPaths
    draw_repository: SQLiteDrawRepository
    future_draw_reader: SQLiteFutureDrawIdentityReader
    prediction_store: FileSystemProspectiveObservationStore
    ledger_store: FileSystemForwardEvidenceLedgerStore
    seal_service: RunnablePredictionSealService
    join_service: ProspectiveResultJoinService
    ledger_service: ForwardEvidenceLedgerService
    runner: SingleGameRecurringRunner


@dataclass(frozen=True, slots=True)
class T539P638RecurringAutomationComposition:
    """Resolved unified multi-game composition for T539 and P638."""

    data_paths: LocalDataPaths
    draw_repository: SQLiteDrawRepository
    future_draw_reader: SQLiteFutureDrawIdentityReader
    prediction_store: FileSystemProspectiveObservationStore
    ledger_store: FileSystemForwardEvidenceLedgerStore
    t539_composition: SingleGameRecurringComposition
    p638_composition: SingleGameRecurringComposition
    service: T539P638RecurringAutomationService


def compose_single_game_recurring_runner(
    *,
    lottery_type: LotteryType,
    data_directory: Path,
    prediction_store_root: Path,
    ledger_store_root: Path,
    connection: sqlite3.Connection,
    cohort: FrozenCohortRef,
    producer_factory: ScheduledPredictionProducerFactory,
    base_producer_fingerprint: ProducerFingerprint,
    clock: Callable[[], datetime] | None = None,
) -> SingleGameRecurringComposition:
    """Compose a SingleGameRecurringRunner backed by open SQLite and filesystem stores."""
    if type(lottery_type) is not LotteryType or lottery_type not in _SUPPORTED_LOTTERIES:
        raise ValueError("Recurring automation supports only DAILY_539 and POWER_LOTTO")
    selected_data_directory = _require_absolute_path(data_directory, "data_directory")
    selected_prediction_root = _require_absolute_path(
        prediction_store_root, "prediction_store_root"
    )
    selected_ledger_root = _require_absolute_path(ledger_store_root, "ledger_store_root")
    if type(connection) is not sqlite3.Connection:
        raise ValueError("connection must be an open sqlite3.Connection")
    if type(cohort) is not FrozenCohortRef or cohort.lottery_type is not lottery_type:
        raise ValueError("cohort must match the configured lottery type")
    if type(base_producer_fingerprint) is not ProducerFingerprint:
        raise ValueError("base_producer_fingerprint must be a ProducerFingerprint")

    selected_clock = _utc_now if clock is None else clock
    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(selected_data_directory)})

    draw_repository = SQLiteDrawRepository(connection)
    future_draw_reader = SQLiteFutureDrawIdentityReader(paths)
    prediction_store = FileSystemProspectiveObservationStore(selected_prediction_root)
    ledger_store = FileSystemForwardEvidenceLedgerStore(selected_ledger_root)

    target_authority = compose_pre_outcome_target_operational_service(
        environ={DATA_DIRECTORY_ENV: str(selected_data_directory)},
        clock=selected_clock,
    )
    contracts = repository_game_contracts()

    seal_service = RunnablePredictionSealService(
        lottery_type=lottery_type,
        registration_service=target_authority.service,
        store=prediction_store,
        producer_factory=producer_factory,
        cohort=cohort,
        base_producer_fingerprint=base_producer_fingerprint,
        game_contracts={lottery_type: contracts[lottery_type]},
        clock=selected_clock,
    )

    scoring_service = ScoringPhaseService(
        store=prediction_store,
        game_contracts={lottery_type: contracts[lottery_type]},
        clock=selected_clock,
    )

    join_service = ProspectiveResultJoinService(
        draw_reader=draw_repository,
        scoring_service=scoring_service,
        store=prediction_store,
    )

    ledger_service = ForwardEvidenceLedgerService(
        store=ledger_store,
        clock=selected_clock,
    )

    runner = SingleGameRecurringRunner(
        lottery_type=lottery_type,
        future_draw_reader=future_draw_reader,
        seal_service=seal_service,
        prediction_store=prediction_store,
        join_service=join_service,
        ledger_service=ledger_service,
        cohort=cohort,
        base_producer_fingerprint=base_producer_fingerprint,
        clock=selected_clock,
    )

    return SingleGameRecurringComposition(
        lottery_type=lottery_type,
        data_paths=paths,
        draw_repository=draw_repository,
        future_draw_reader=future_draw_reader,
        prediction_store=prediction_store,
        ledger_store=ledger_store,
        seal_service=seal_service,
        join_service=join_service,
        ledger_service=ledger_service,
        runner=runner,
    )


def compose_t539_p638_recurring_automation(
    *,
    data_directory: Path,
    prediction_store_root: Path,
    ledger_store_root: Path,
    connection: sqlite3.Connection,
    t539_cohort: FrozenCohortRef,
    t539_producer_factory: ScheduledPredictionProducerFactory,
    t539_base_producer_fingerprint: ProducerFingerprint,
    p638_cohort: FrozenCohortRef,
    p638_producer_factory: ScheduledPredictionProducerFactory,
    p638_base_producer_fingerprint: ProducerFingerprint,
    clock: Callable[[], datetime] | None = None,
) -> T539P638RecurringAutomationComposition:
    """Compose the multi-game recurring automation service for DAILY_539 and POWER_LOTTO."""
    selected_clock = _utc_now if clock is None else clock

    t539_comp = compose_single_game_recurring_runner(
        lottery_type=LotteryType.DAILY_539,
        data_directory=data_directory,
        prediction_store_root=prediction_store_root,
        ledger_store_root=ledger_store_root,
        connection=connection,
        cohort=t539_cohort,
        producer_factory=t539_producer_factory,
        base_producer_fingerprint=t539_base_producer_fingerprint,
        clock=selected_clock,
    )

    p638_comp = compose_single_game_recurring_runner(
        lottery_type=LotteryType.POWER_LOTTO,
        data_directory=data_directory,
        prediction_store_root=prediction_store_root,
        ledger_store_root=ledger_store_root,
        connection=connection,
        cohort=p638_cohort,
        producer_factory=p638_producer_factory,
        base_producer_fingerprint=p638_base_producer_fingerprint,
        clock=selected_clock,
    )

    service = T539P638RecurringAutomationService(
        runners={
            LotteryType.DAILY_539: t539_comp.runner,
            LotteryType.POWER_LOTTO: p638_comp.runner,
        },
        clock=selected_clock,
    )

    return T539P638RecurringAutomationComposition(
        data_paths=t539_comp.data_paths,
        draw_repository=t539_comp.draw_repository,
        future_draw_reader=t539_comp.future_draw_reader,
        prediction_store=t539_comp.prediction_store,
        ledger_store=t539_comp.ledger_store,
        t539_composition=t539_comp,
        p638_composition=p638_comp,
        service=service,
    )


@contextmanager
def open_t539_p638_recurring_automation(
    *,
    data_directory: Path,
    prediction_store_root: Path,
    ledger_store_root: Path,
    t539_cohort: FrozenCohortRef,
    t539_producer_factory: ScheduledPredictionProducerFactory,
    t539_base_producer_fingerprint: ProducerFingerprint,
    p638_cohort: FrozenCohortRef,
    p638_producer_factory: ScheduledPredictionProducerFactory,
    p638_base_producer_fingerprint: ProducerFingerprint,
    clock: Callable[[], datetime] | None = None,
    read_only: bool = False,
) -> Generator[T539P638RecurringAutomationComposition]:
    """Open and yield a Stage H composition backed by an open SQLite database connection."""
    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(data_directory)})
    with open_database(paths, read_only=read_only) as connection:
        yield compose_t539_p638_recurring_automation(
            data_directory=data_directory,
            prediction_store_root=prediction_store_root,
            ledger_store_root=ledger_store_root,
            connection=connection,
            t539_cohort=t539_cohort,
            t539_producer_factory=t539_producer_factory,
            t539_base_producer_fingerprint=t539_base_producer_fingerprint,
            p638_cohort=p638_cohort,
            p638_producer_factory=p638_producer_factory,
            p638_base_producer_fingerprint=p638_base_producer_fingerprint,
            clock=clock,
        )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_absolute_path(value: object, label: str) -> Path:
    if not isinstance(value, Path) or not value.is_absolute():
        raise ValueError(f"{label} must be an absolute Path")
    return value


__all__ = [
    "SingleGameRecurringComposition",
    "T539P638RecurringAutomationComposition",
    "compose_single_game_recurring_runner",
    "compose_t539_p638_recurring_automation",
    "open_t539_p638_recurring_automation",
]
