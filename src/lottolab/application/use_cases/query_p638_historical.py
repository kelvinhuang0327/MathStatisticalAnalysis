"""Validated application use cases for the P638 Historical Results API."""

from __future__ import annotations

from lottolab.application.p638_historical import (
    P638_QUERY_STATUS_ALIASES,
    P638CurrentRankingPage,
    P638DrawPage,
    P638DrawRecord,
    P638HistoricalQueryError,
    P638RankingPage,
    P638ReplayPage,
    P638ReplayQuery,
    P638RunPage,
    P638StrategyMetrics,
    P638StrategyPage,
    P638TargetDetail,
)
from lottolab.application.ports import (
    P638All10RankingQueryRepositoryFactory,
    P638All23RankingQueryRepositoryFactory,
    P638CurrentRankingQueryRepositoryFactory,
    P638HistoricalQueryRepositoryFactory,
)

MIN_LIMIT = 1
MAX_LIMIT = 200


def _validate_page(limit: int, offset: int) -> None:
    if not MIN_LIMIT <= limit <= MAX_LIMIT:
        raise P638HistoricalQueryError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}")
    if offset < 0:
        raise P638HistoricalQueryError("offset must be non-negative")


def _validate_run_id(run_id: str) -> None:
    if not run_id or len(run_id) > 128:
        raise P638HistoricalQueryError("run_id is invalid")


class ListP638Runs:
    def __init__(self, repository_factory: P638HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, *, limit: int = 50, offset: int = 0) -> P638RunPage:
        _validate_page(limit, offset)
        return self._repository_factory().list_runs(limit=limit, offset=offset)


class ListP638Strategies:
    def __init__(self, repository_factory: P638HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str, *, limit: int = 200, offset: int = 0) -> P638StrategyPage | None:
        _validate_run_id(run_id)
        _validate_page(limit, offset)
        return self._repository_factory().list_strategies(run_id, limit=limit, offset=offset)


class ListP638Draws:
    def __init__(self, repository_factory: P638HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str, *, limit: int = 50, offset: int = 0) -> P638DrawPage | None:
        _validate_run_id(run_id)
        _validate_page(limit, offset)
        return self._repository_factory().list_draws(run_id, limit=limit, offset=offset)


class GetP638Draw:
    def __init__(self, repository_factory: P638HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str, draw_number: str) -> P638DrawRecord | None:
        _validate_run_id(run_id)
        if not draw_number or len(draw_number) > 128:
            raise P638HistoricalQueryError("draw_number is invalid")
        return self._repository_factory().get_draw(run_id, draw_number)


class ListP638Replay:
    def __init__(self, repository_factory: P638HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(
        self,
        run_id: str,
        *,
        strategy_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> P638ReplayPage | None:
        _validate_run_id(run_id)
        _validate_page(limit, offset)
        if strategy_id is not None and not strategy_id:
            raise P638HistoricalQueryError("strategy_id is invalid")
        if date_from is not None and date_to is not None and date_from > date_to:
            raise P638HistoricalQueryError("date_from must not be after date_to")
        if status is not None and status not in P638_QUERY_STATUS_ALIASES:
            raise P638HistoricalQueryError("status is invalid")
        return self._repository_factory().list_replay(
            run_id,
            P638ReplayQuery(
                strategy_id=strategy_id,
                date_from=date_from,
                date_to=date_to,
                status=status,
                limit=limit,
                offset=offset,
            ),
        )


class GetP638Target:
    def __init__(self, repository_factory: P638HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str, target_id: str) -> P638TargetDetail | None:
        _validate_run_id(run_id)
        if not target_id or len(target_id) > 128:
            raise P638HistoricalQueryError("target_id is invalid")
        return self._repository_factory().get_target(run_id, target_id)


class GetP638TargetByIdentity:
    def __init__(self, repository_factory: P638HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(
        self, run_id: str, strategy_id: str, strategy_version: str, draw_number: str
    ) -> P638TargetDetail | None:
        _validate_run_id(run_id)
        if not strategy_id or len(strategy_id) > 200:
            raise P638HistoricalQueryError("strategy_id is invalid")
        if not strategy_version or len(strategy_version) > 200:
            raise P638HistoricalQueryError("strategy_version is invalid")
        if not draw_number or len(draw_number) > 128:
            raise P638HistoricalQueryError("draw_number is invalid")
        return self._repository_factory().get_target_by_identity(
            run_id, strategy_id, strategy_version, draw_number
        )


class GetP638Metrics:
    def __init__(self, repository_factory: P638HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str, *, strategy_id: str | None = None) -> P638StrategyMetrics | None:
        _validate_run_id(run_id)
        if strategy_id is not None and not strategy_id:
            raise P638HistoricalQueryError("strategy_id is invalid")
        return self._repository_factory().get_metrics(run_id, strategy_id=strategy_id)


class ListP638Rankings:
    """All-10 official-prize historical ranking, distinct from the P638 V2 projection."""

    def __init__(self, repository_factory: P638All10RankingQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str) -> P638RankingPage | None:
        _validate_run_id(run_id)
        return self._repository_factory().list_rankings(run_id)


class ListP638All23Rankings:
    """All-23 official-prize historical ranking, distinct from the V2 and all-10 projections."""

    def __init__(self, repository_factory: P638All23RankingQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str) -> P638RankingPage | None:
        _validate_run_id(run_id)
        return self._repository_factory().list_rankings(run_id)


class ListP638CurrentRankings:
    """Current-universe official-prize historical ranking (grows across waves)."""

    def __init__(self, repository_factory: P638CurrentRankingQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str) -> P638CurrentRankingPage | None:
        _validate_run_id(run_id)
        return self._repository_factory().list_rankings(run_id)
