"""Local-only FastAPI composition for an explicit Historical Results database."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Never

from fastapi import FastAPI

from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessWindowsUnavailableError,
)
from lottolab.application.historical_queries import HistoricalResultsUnavailableError
from lottolab.application.ports import (
    HistoricalPrefixSuccessWindowSourceReader,
    HistoricalResultQueryRepository,
)
from lottolab.infrastructure.persistence.historical_prefix_success_window_reader import (
    SQLiteHistoricalPrefixSuccessWindowSourceReader,
)
from lottolab.infrastructure.persistence.historical_repositories import (
    SQLiteHistoricalResultQueryRepository,
)
from lottolab.infrastructure.persistence.historical_schema import verify_schema_read_only
from lottolab.interfaces.api.app import create_app

HISTORICAL_RESULTS_DB_ENV = "LOTTOLAB_HISTORICAL_RESULTS_DB"


@dataclass(frozen=True)
class LocalHistoricalComposition:
    """Two lazy read-only factories bound to one exact configured path."""

    database: Path

    def historical_query_repository(self) -> HistoricalResultQueryRepository:
        self._require_available(for_success_windows=False)
        return SQLiteHistoricalResultQueryRepository(self.database)

    def historical_prefix_success_window_source_reader(
        self,
    ) -> HistoricalPrefixSuccessWindowSourceReader:
        self._require_available(for_success_windows=True)
        return SQLiteHistoricalPrefixSuccessWindowSourceReader(self.database)

    def _require_available(self, *, for_success_windows: bool) -> None:
        try:
            available = verify_schema_read_only(self.database)
        except Exception as exc:
            self._raise_unavailable(for_success_windows=for_success_windows, cause=exc)
        if not available:
            self._raise_unavailable(for_success_windows=for_success_windows)

    @staticmethod
    def _raise_unavailable(
        *, for_success_windows: bool, cause: BaseException | None = None
    ) -> Never:
        message = "configured historical results storage is unavailable"
        if for_success_windows:
            raise HistoricalPrefixSuccessWindowsUnavailableError(message) from cause
        raise HistoricalResultsUnavailableError(message) from cause


def local_historical_composition(
    environment: Mapping[str, str],
) -> LocalHistoricalComposition | None:
    """Resolve one exact optional value without trimming, guessing, or filesystem access."""

    configured = environment.get(HISTORICAL_RESULTS_DB_ENV)
    if configured is None or configured == "":
        return None
    return LocalHistoricalComposition(database=Path(configured))


def create_local_app() -> FastAPI:
    """Compose the normal local app without opening or modifying any database."""

    composition = local_historical_composition(os.environ)
    if composition is None:
        return create_app()
    return create_app(
        historical_query_repository_factory=composition.historical_query_repository,
        historical_prefix_success_window_source_reader_factory=(
            composition.historical_prefix_success_window_source_reader
        ),
    )


__all__ = [
    "HISTORICAL_RESULTS_DB_ENV",
    "LocalHistoricalComposition",
    "create_local_app",
    "local_historical_composition",
]
