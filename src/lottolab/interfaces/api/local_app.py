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
    DrawDataProvider,
    HistoricalPrefixSuccessWindowSourceReader,
    HistoricalResultQueryRepository,
    ReplayScoringProjectionReader,
)
from lottolab.application.use_cases.query_replay_scoring_projection import (
    ReplayScoringQueryUnavailableError,
)
from lottolab.infrastructure.draw_provider import JsonHttpDrawDataProvider
from lottolab.infrastructure.persistence.historical_prefix_success_window_reader import (
    SQLiteHistoricalPrefixSuccessWindowSourceReader,
)
from lottolab.infrastructure.persistence.historical_repositories import (
    SQLiteHistoricalResultQueryRepository,
)
from lottolab.infrastructure.persistence.historical_schema import verify_schema_read_only
from lottolab.infrastructure.persistence.replay_scoring_projection_repository import (
    SQLiteReplayScoringProjectionRepository,
)
from lottolab.infrastructure.persistence.replay_scoring_schema import (
    verify_schema_read_only as verify_replay_scoring_schema_read_only,
)
from lottolab.interfaces.api.app import create_app

HISTORICAL_RESULTS_DB_ENV = "LOTTOLAB_HISTORICAL_RESULTS_DB"
DRAW_PROVIDER_URL_ENV = "LOTTOLAB_DRAW_PROVIDER_URL"
REPLAY_SCORING_DB_ENV = "LOTTOLAB_REPLAY_SCORING_DB"


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


@dataclass(frozen=True)
class LocalReplayScoringComposition:
    """One lazy read-only factory bound to one exact configured path."""

    database: Path

    def replay_scoring_projection_reader(self) -> ReplayScoringProjectionReader:
        try:
            available = verify_replay_scoring_schema_read_only(self.database)
        except Exception as exc:
            raise ReplayScoringQueryUnavailableError(
                "configured replay-scoring storage is unavailable"
            ) from exc
        if not available:
            raise ReplayScoringQueryUnavailableError(
                "configured replay-scoring storage is unavailable"
            )
        return SQLiteReplayScoringProjectionRepository(self.database)


def local_replay_scoring_composition(
    environment: Mapping[str, str],
) -> LocalReplayScoringComposition | None:
    """Resolve one exact optional value without trimming, guessing, or filesystem access."""

    configured = environment.get(REPLAY_SCORING_DB_ENV)
    if configured is None or configured == "":
        return None
    return LocalReplayScoringComposition(database=Path(configured))


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
    replay_scoring_composition = local_replay_scoring_composition(os.environ)
    provider = local_draw_provider(os.environ)
    replay_scoring_projection_reader_factory = (
        replay_scoring_composition.replay_scoring_projection_reader
        if replay_scoring_composition is not None
        else None
    )
    if composition is None:
        return create_app(
            draw_data_provider_factory=lambda: provider,
            replay_scoring_projection_reader_factory=replay_scoring_projection_reader_factory,
        )
    return create_app(
        draw_data_provider_factory=lambda: provider,
        historical_query_repository_factory=composition.historical_query_repository,
        historical_prefix_success_window_source_reader_factory=(
            composition.historical_prefix_success_window_source_reader
        ),
        replay_scoring_projection_reader_factory=replay_scoring_projection_reader_factory,
    )


def local_draw_provider(
    environment: Mapping[str, str],
) -> DrawDataProvider | None:
    """Resolve an optional provider adapter without making a network request."""

    configured = environment.get(DRAW_PROVIDER_URL_ENV)
    if configured is None or configured == "":
        return None
    return JsonHttpDrawDataProvider(configured)


__all__ = [
    "DRAW_PROVIDER_URL_ENV",
    "HISTORICAL_RESULTS_DB_ENV",
    "REPLAY_SCORING_DB_ENV",
    "LocalHistoricalComposition",
    "LocalReplayScoringComposition",
    "create_local_app",
    "local_draw_provider",
    "local_historical_composition",
    "local_replay_scoring_composition",
]
