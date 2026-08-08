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
    P638All10RankingQueryRepository,
    P638All23RankingQueryRepository,
    P638HistoricalQueryRepository,
    ReplayScoringProjectionReader,
    T539HistoricalQueryRepository,
)
from lottolab.application.t539_historical import T539HistoricalResultsUnavailableError
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
from lottolab.infrastructure.persistence.p638_all10_ranking_repositories import (
    SQLiteP638All10RankingQueryRepository,
)
from lottolab.infrastructure.persistence.p638_all10_ranking_schema import (
    verify_schema_read_only as verify_p638_all10_ranking_schema_read_only,
)
from lottolab.infrastructure.persistence.p638_all23_ranking_repositories import (
    SQLiteP638All23RankingQueryRepository,
)
from lottolab.infrastructure.persistence.p638_all23_ranking_schema import (
    verify_schema_read_only as verify_p638_all23_ranking_schema_read_only,
)
from lottolab.infrastructure.persistence.p638_historical_repositories import (
    SQLiteP638HistoricalQueryRepository,
)
from lottolab.infrastructure.persistence.replay_scoring_projection_repository import (
    SQLiteReplayScoringProjectionRepository,
)
from lottolab.infrastructure.persistence.replay_scoring_schema import (
    verify_schema_read_only as verify_replay_scoring_schema_read_only,
)
from lottolab.infrastructure.persistence.t539_historical_repositories import (
    SQLiteT539HistoricalQueryRepository,
)
from lottolab.infrastructure.persistence.t539_historical_repositories import (
    verify_schema_read_only as verify_t539_historical_schema_read_only,
)
from lottolab.infrastructure.taiwan_lottery_draw_provider import TaiwanLotteryDrawProvider
from lottolab.interfaces.api.app import create_app

HISTORICAL_RESULTS_DB_ENV = "LOTTOLAB_HISTORICAL_RESULTS_DB"
P638_ALL10_RANKING_DB_ENV = "LOTTOLAB_P638_ALL10_RANKING_DB"
P638_ALL23_RANKING_DB_ENV = "LOTTOLAB_P638_ALL23_RANKING_DB"
T539_HISTORICAL_DB_ENV = "LOTTOLAB_T539_HISTORICAL_DB"
DRAW_PROVIDER_URL_ENV = "LOTTOLAB_DRAW_PROVIDER_URL"
DRAW_PROVIDER_SOURCE_ENV = "LOTTOLAB_DRAW_PROVIDER_SOURCE"
OFFICIAL_TAIWAN_LOTTERY_SOURCE = "OFFICIAL_TAIWAN_LOTTERY"
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

    def p638_historical_query_repository(self) -> P638HistoricalQueryRepository:
        self._require_available(for_success_windows=False)
        return SQLiteP638HistoricalQueryRepository(self.database)

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


@dataclass(frozen=True)
class LocalP638All10RankingComposition:
    """One lazy read-only factory bound to the separate all-10 ranking database.

    Distinct from ``LocalHistoricalComposition``: that composition reads the
    frozen P638 Historical Results V2 database. This composition reads the
    separate all-10 executable-strategy official-prize ranking database,
    never the same file.
    """

    database: Path

    def p638_all10_ranking_query_repository(self) -> P638All10RankingQueryRepository:
        try:
            available = verify_p638_all10_ranking_schema_read_only(self.database)
        except Exception as exc:
            raise HistoricalResultsUnavailableError(
                "configured P638 all-10 ranking storage is unavailable"
            ) from exc
        if not available:
            raise HistoricalResultsUnavailableError(
                "configured P638 all-10 ranking storage is unavailable"
            )
        return SQLiteP638All10RankingQueryRepository(self.database)


def local_p638_all10_ranking_composition(
    environment: Mapping[str, str],
) -> LocalP638All10RankingComposition | None:
    """Resolve one exact optional value without trimming, guessing, or filesystem access."""

    configured = environment.get(P638_ALL10_RANKING_DB_ENV)
    if configured is None or configured == "":
        return None
    return LocalP638All10RankingComposition(database=Path(configured))


@dataclass(frozen=True)
class LocalP638All23RankingComposition:
    """One lazy read-only factory bound to the separate all-23 ranking database.

    Distinct from ``LocalHistoricalComposition`` and from
    ``LocalP638All10RankingComposition``: this composition reads the
    separate all-23 executable-strategy (Wave 1's 10 plus Wave 2's 13)
    official-prize ranking database, never the V2 or all-10 file.
    """

    database: Path

    def p638_all23_ranking_query_repository(self) -> P638All23RankingQueryRepository:
        try:
            available = verify_p638_all23_ranking_schema_read_only(self.database)
        except Exception as exc:
            raise HistoricalResultsUnavailableError(
                "configured P638 all-23 ranking storage is unavailable"
            ) from exc
        if not available:
            raise HistoricalResultsUnavailableError(
                "configured P638 all-23 ranking storage is unavailable"
            )
        return SQLiteP638All23RankingQueryRepository(self.database)


def local_p638_all23_ranking_composition(
    environment: Mapping[str, str],
) -> LocalP638All23RankingComposition | None:
    """Resolve one exact optional value without trimming, guessing, or filesystem access."""

    configured = environment.get(P638_ALL23_RANKING_DB_ENV)
    if configured is None or configured == "":
        return None
    return LocalP638All23RankingComposition(database=Path(configured))


@dataclass(frozen=True)
class LocalT539HistoricalComposition:
    """One lazy read-only factory bound to the sealed T539 Wave 1 database.

    Distinct from ``LocalHistoricalComposition``: T539 Wave 1 has its own
    flat schema and its own database file, never the shared Historical
    Results projection P638 reads.
    """

    database: Path

    def t539_historical_query_repository(self) -> T539HistoricalQueryRepository:
        try:
            available = verify_t539_historical_schema_read_only(self.database)
        except Exception as exc:
            raise T539HistoricalResultsUnavailableError(
                "configured T539 Wave 1 storage is unavailable"
            ) from exc
        if not available:
            raise T539HistoricalResultsUnavailableError(
                "configured T539 Wave 1 storage is unavailable"
            )
        return SQLiteT539HistoricalQueryRepository(self.database)


def local_t539_historical_composition(
    environment: Mapping[str, str],
) -> LocalT539HistoricalComposition | None:
    """Resolve one exact optional value without trimming, guessing, or filesystem access."""

    configured = environment.get(T539_HISTORICAL_DB_ENV)
    if configured is None or configured == "":
        return None
    return LocalT539HistoricalComposition(database=Path(configured))


def create_local_app() -> FastAPI:
    """Compose the normal local app without opening or modifying any database."""

    composition = local_historical_composition(os.environ)
    replay_scoring_composition = local_replay_scoring_composition(os.environ)
    all10_ranking_composition = local_p638_all10_ranking_composition(os.environ)
    all23_ranking_composition = local_p638_all23_ranking_composition(os.environ)
    t539_historical_composition = local_t539_historical_composition(os.environ)
    provider = local_draw_provider(os.environ)
    replay_scoring_projection_reader_factory = (
        replay_scoring_composition.replay_scoring_projection_reader
        if replay_scoring_composition is not None
        else None
    )
    all10_ranking_factory = (
        None
        if all10_ranking_composition is None
        else all10_ranking_composition.p638_all10_ranking_query_repository
    )
    all23_ranking_factory = (
        None
        if all23_ranking_composition is None
        else all23_ranking_composition.p638_all23_ranking_query_repository
    )
    t539_historical_query_repository_factory = (
        None
        if t539_historical_composition is None
        else t539_historical_composition.t539_historical_query_repository
    )
    if composition is None:
        return create_app(
            draw_data_provider_factory=lambda: provider,
            replay_scoring_projection_reader_factory=replay_scoring_projection_reader_factory,
            p638_all10_ranking_query_repository_factory=all10_ranking_factory,
            p638_all23_ranking_query_repository_factory=all23_ranking_factory,
            t539_historical_query_repository_factory=t539_historical_query_repository_factory,
        )
    return create_app(
        draw_data_provider_factory=lambda: provider,
        historical_query_repository_factory=composition.historical_query_repository,
        p638_historical_query_repository_factory=composition.p638_historical_query_repository,
        historical_prefix_success_window_source_reader_factory=(
            composition.historical_prefix_success_window_source_reader
        ),
        replay_scoring_projection_reader_factory=replay_scoring_projection_reader_factory,
        p638_all10_ranking_query_repository_factory=all10_ranking_factory,
        p638_all23_ranking_query_repository_factory=all23_ranking_factory,
        t539_historical_query_repository_factory=t539_historical_query_repository_factory,
    )


def local_draw_provider(
    environment: Mapping[str, str],
) -> DrawDataProvider | None:
    """Resolve an optional provider adapter without making a network request.

    An explicit ``LOTTOLAB_DRAW_PROVIDER_URL`` always wins (a caller-owned
    JSON endpoint, e.g. for local testing). Otherwise, opting in to
    ``LOTTOLAB_DRAW_PROVIDER_SOURCE=OFFICIAL_TAIWAN_LOTTERY`` wires the
    official Taiwan Lottery API adapter. With neither set, this returns
    ``None`` and draw-sync stays fail-closed, unchanged from before.
    """

    configured_url = environment.get(DRAW_PROVIDER_URL_ENV)
    if configured_url:
        return JsonHttpDrawDataProvider(configured_url)
    if environment.get(DRAW_PROVIDER_SOURCE_ENV) == OFFICIAL_TAIWAN_LOTTERY_SOURCE:
        return TaiwanLotteryDrawProvider()
    return None


__all__ = [
    "DRAW_PROVIDER_SOURCE_ENV",
    "DRAW_PROVIDER_URL_ENV",
    "HISTORICAL_RESULTS_DB_ENV",
    "OFFICIAL_TAIWAN_LOTTERY_SOURCE",
    "REPLAY_SCORING_DB_ENV",
    "T539_HISTORICAL_DB_ENV",
    "LocalHistoricalComposition",
    "LocalReplayScoringComposition",
    "LocalT539HistoricalComposition",
    "create_local_app",
    "local_draw_provider",
    "local_historical_composition",
    "local_replay_scoring_composition",
    "local_t539_historical_composition",
]
