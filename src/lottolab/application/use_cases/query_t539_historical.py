"""Validated application use cases for the T539 Wave 1 Strategy Analysis API."""

from __future__ import annotations

from lottolab.application.ports import T539HistoricalQueryRepositoryFactory
from lottolab.application.t539_historical import (
    T539_QUERY_STATUS_ALIASES,
    T539CoverageLedger,
    T539DrawPage,
    T539DrawRecord,
    T539HistoricalQueryError,
    T539RankingPage,
    T539ReplayPage,
    T539ReplayQuery,
    T539RunPage,
    T539StrategyMetrics,
    T539StrategyPage,
    T539TargetDetail,
)

MIN_LIMIT = 1
MAX_LIMIT = 200


def _validate_page(limit: int, offset: int) -> None:
    if not MIN_LIMIT <= limit <= MAX_LIMIT:
        raise T539HistoricalQueryError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}")
    if offset < 0:
        raise T539HistoricalQueryError("offset must be non-negative")


def _validate_run_id(run_id: str) -> None:
    if not run_id or len(run_id) > 128:
        raise T539HistoricalQueryError("run_id is invalid")


class ListT539Runs:
    def __init__(self, repository_factory: T539HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, *, limit: int = 50, offset: int = 0) -> T539RunPage:
        _validate_page(limit, offset)
        return self._repository_factory().list_runs(limit=limit, offset=offset)


class ListT539Strategies:
    def __init__(self, repository_factory: T539HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str, *, limit: int = 200, offset: int = 0) -> T539StrategyPage | None:
        _validate_run_id(run_id)
        _validate_page(limit, offset)
        return self._repository_factory().list_strategies(run_id, limit=limit, offset=offset)


class ListT539Draws:
    def __init__(self, repository_factory: T539HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str, *, limit: int = 50, offset: int = 0) -> T539DrawPage | None:
        _validate_run_id(run_id)
        _validate_page(limit, offset)
        return self._repository_factory().list_draws(run_id, limit=limit, offset=offset)


class GetT539Draw:
    def __init__(self, repository_factory: T539HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str, draw_id: str) -> T539DrawRecord | None:
        _validate_run_id(run_id)
        if not draw_id or len(draw_id) > 128:
            raise T539HistoricalQueryError("draw_id is invalid")
        return self._repository_factory().get_draw(run_id, draw_id)


class ListT539Replay:
    def __init__(self, repository_factory: T539HistoricalQueryRepositoryFactory) -> None:
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
    ) -> T539ReplayPage | None:
        _validate_run_id(run_id)
        _validate_page(limit, offset)
        if strategy_id is not None and not strategy_id:
            raise T539HistoricalQueryError("strategy_id is invalid")
        if date_from is not None and date_to is not None and date_from > date_to:
            raise T539HistoricalQueryError("date_from must not be after date_to")
        if status is not None and status not in T539_QUERY_STATUS_ALIASES:
            raise T539HistoricalQueryError("status is invalid")
        return self._repository_factory().list_replay(
            run_id,
            T539ReplayQuery(
                strategy_id=strategy_id,
                date_from=date_from,
                date_to=date_to,
                status=status,
                limit=limit,
                offset=offset,
            ),
        )


class GetT539Target:
    def __init__(self, repository_factory: T539HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str, target_id: str) -> T539TargetDetail | None:
        _validate_run_id(run_id)
        if not target_id or len(target_id) > 128:
            raise T539HistoricalQueryError("target_id is invalid")
        return self._repository_factory().get_target(run_id, target_id)


class GetT539Metrics:
    def __init__(self, repository_factory: T539HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str, *, strategy_id: str | None = None) -> T539StrategyMetrics | None:
        _validate_run_id(run_id)
        if strategy_id is not None and not strategy_id:
            raise T539HistoricalQueryError("strategy_id is invalid")
        return self._repository_factory().get_metrics(run_id, strategy_id=strategy_id)


class ListT539Rankings:
    """Official-prize historical ranking of the eight executed Wave 1 strategies."""

    def __init__(self, repository_factory: T539HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str) -> T539RankingPage | None:
        _validate_run_id(run_id)
        return self._repository_factory().list_rankings(run_id)


class GetT539CoverageLedger:
    """The complete Wave 1 coverage ledger, including every blocked identity."""

    def __init__(self, repository_factory: T539HistoricalQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str) -> T539CoverageLedger | None:
        _validate_run_id(run_id)
        return self._repository_factory().get_coverage_ledger(run_id)
