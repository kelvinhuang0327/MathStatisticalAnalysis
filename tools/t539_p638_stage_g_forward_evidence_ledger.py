"""One-shot Stage G composition for T539/P638 forward evidence ledgers.

This module composes the canonical draw repository, prospective prediction/score store,
Stage E result joiner, and durable forward evidence ledger into a deterministic,
append-only pipeline for DAILY_539 and POWER_LOTTO.
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
from lottolab.application.prospective_result_join import (
    ProspectiveResultJoinService,
)
from lottolab.domain.draws import LotteryType
from lottolab.infrastructure.forward_evidence_ledger_store import (
    FileSystemForwardEvidenceLedgerStore,
)
from lottolab.infrastructure.persistence.draw_schema import (
    DATA_DIRECTORY_ENV,
    LocalDataPaths,
    open_database,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.repositories import SQLiteDrawRepository
from lottolab.infrastructure.prospective_observer_store import (
    FileSystemProspectiveObservationStore,
)

_SUPPORTED_LOTTERIES = frozenset({LotteryType.DAILY_539, LotteryType.POWER_LOTTO})


@dataclass(frozen=True, slots=True)
class T539P638StageGComposition:
    """Resolved draw repository, prediction/score store, ledger store, and forward service."""

    data_paths: LocalDataPaths
    draw_repository: SQLiteDrawRepository
    prediction_store: FileSystemProspectiveObservationStore
    ledger_store: FileSystemForwardEvidenceLedgerStore
    scoring_service: ScoringPhaseService
    result_join_service: ProspectiveResultJoinService
    ledger_service: ForwardEvidenceLedgerService


def compose_t539_p638_stage_g_forward_evidence_ledger(
    *,
    lottery_type: LotteryType,
    data_directory: Path,
    prediction_store_root: Path,
    ledger_store_root: Path,
    connection: sqlite3.Connection,
    clock: Callable[[], datetime] | None = None,
) -> T539P638StageGComposition:
    """Compose Stage G for DAILY_539 or POWER_LOTTO over an open draw connection."""
    if type(lottery_type) is not LotteryType or lottery_type not in _SUPPORTED_LOTTERIES:
        raise ValueError("Stage G composition supports only DAILY_539 and POWER_LOTTO")
    selected_data_directory = _require_absolute_path(data_directory, "data_directory")
    selected_prediction_root = _require_absolute_path(
        prediction_store_root,
        "prediction_store_root",
    )
    selected_ledger_root = _require_absolute_path(
        ledger_store_root,
        "ledger_store_root",
    )
    if type(connection) is not sqlite3.Connection:
        raise ValueError("connection must be an open sqlite3.Connection")

    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(selected_data_directory)})
    draw_repository = SQLiteDrawRepository(connection)
    prediction_store = FileSystemProspectiveObservationStore(selected_prediction_root)
    ledger_store = FileSystemForwardEvidenceLedgerStore(selected_ledger_root)
    contracts = repository_game_contracts()
    selected_clock = _utc_now if clock is None else clock

    scoring_service = ScoringPhaseService(
        store=prediction_store,
        game_contracts={lottery_type: contracts[lottery_type]},
        clock=selected_clock,
    )
    result_join_service = ProspectiveResultJoinService(
        draw_reader=draw_repository,
        scoring_service=scoring_service,
        store=prediction_store,
    )
    ledger_service = ForwardEvidenceLedgerService(
        store=ledger_store,
        clock=selected_clock,
    )

    return T539P638StageGComposition(
        data_paths=paths,
        draw_repository=draw_repository,
        prediction_store=prediction_store,
        ledger_store=ledger_store,
        scoring_service=scoring_service,
        result_join_service=result_join_service,
        ledger_service=ledger_service,
    )


@contextmanager
def open_t539_p638_stage_g_forward_evidence_ledger(
    *,
    lottery_type: LotteryType,
    data_directory: Path,
    prediction_store_root: Path,
    ledger_store_root: Path,
    clock: Callable[[], datetime] | None = None,
    read_only: bool = True,
) -> Generator[T539P638StageGComposition]:
    """Open and yield a Stage G composition backed by an open SQLite database connection."""
    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(data_directory)})
    with open_database(paths, read_only=read_only) as connection:
        yield compose_t539_p638_stage_g_forward_evidence_ledger(
            lottery_type=lottery_type,
            data_directory=data_directory,
            prediction_store_root=prediction_store_root,
            ledger_store_root=ledger_store_root,
            connection=connection,
            clock=clock,
        )


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _require_absolute_path(value: object, label: str) -> Path:
    if not isinstance(value, Path) or not value.is_absolute():
        raise ValueError(f"{label} must be an absolute Path")
    return value


__all__ = [
    "T539P638StageGComposition",
    "compose_t539_p638_stage_g_forward_evidence_ledger",
    "open_t539_p638_stage_g_forward_evidence_ledger",
]
