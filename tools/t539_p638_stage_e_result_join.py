"""One-shot Stage E composition for T539/P638 prospective result joins.

This module composes the canonical draw repository, durable prediction/score store,
and generic prospective scoring service into a deterministic result joiner for
DAILY_539 and POWER_LOTTO.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from lottolab.application.prospective_observer import (
    ScoringPhaseService,
    repository_game_contracts,
)
from lottolab.application.prospective_result_join import (
    ProspectiveResultJoinService,
)
from lottolab.domain.draws import LotteryType
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
class T539P638StageEComposition:
    """Resolved draw repository, durable prediction/score store, and result-join service."""

    data_paths: LocalDataPaths
    draw_repository: SQLiteDrawRepository
    prediction_store: FileSystemProspectiveObservationStore
    scoring_service: ScoringPhaseService
    service: ProspectiveResultJoinService


def compose_t539_p638_stage_e_result_join(
    *,
    lottery_type: LotteryType,
    data_directory: Path,
    prediction_store_root: Path,
    connection: sqlite3.Connection,
    clock: Callable[[], datetime] | None = None,
) -> T539P638StageEComposition:
    """Compose Stage E for DAILY_539 or POWER_LOTTO over an open draw connection."""
    if type(lottery_type) is not LotteryType or lottery_type not in _SUPPORTED_LOTTERIES:
        raise ValueError("Stage E composition supports only DAILY_539 and POWER_LOTTO")
    selected_data_directory = _require_absolute_path(data_directory, "data_directory")
    selected_prediction_root = _require_absolute_path(
        prediction_store_root,
        "prediction_store_root",
    )
    if type(connection) is not sqlite3.Connection:
        raise ValueError("connection must be an open sqlite3.Connection")

    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(selected_data_directory)})
    draw_repository = SQLiteDrawRepository(connection)
    store = FileSystemProspectiveObservationStore(selected_prediction_root)
    contracts = repository_game_contracts()
    selected_clock = _utc_now if clock is None else clock

    scoring_service = ScoringPhaseService(
        store=store,
        game_contracts={lottery_type: contracts[lottery_type]},
        clock=selected_clock,
    )
    service = ProspectiveResultJoinService(
        draw_reader=draw_repository,
        scoring_service=scoring_service,
        store=store,
    )
    return T539P638StageEComposition(
        data_paths=paths,
        draw_repository=draw_repository,
        prediction_store=store,
        scoring_service=scoring_service,
        service=service,
    )


@contextmanager
def open_t539_p638_stage_e_result_join(
    *,
    lottery_type: LotteryType,
    data_directory: Path,
    prediction_store_root: Path,
    clock: Callable[[], datetime] | None = None,
    read_only: bool = True,
) -> Generator[T539P638StageEComposition]:
    """Open and yield a Stage E composition backed by an open SQLite database connection."""
    paths = resolve_local_data_paths(environ={DATA_DIRECTORY_ENV: str(data_directory)})
    with open_database(paths, read_only=read_only) as connection:
        yield compose_t539_p638_stage_e_result_join(
            lottery_type=lottery_type,
            data_directory=data_directory,
            prediction_store_root=prediction_store_root,
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
    "T539P638StageEComposition",
    "compose_t539_p638_stage_e_result_join",
    "open_t539_p638_stage_e_result_join",
]
