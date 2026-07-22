"""BLHQ R2: read-only use cases for the historical-results query API.

Each use case validates its own parameters (defense in depth alongside the
interfaces layer's FastAPI/Pydantic validation) and otherwise delegates to
the injected :class:`HistoricalResultQueryRepository`. Repository-unavailable
failures propagate as ``HistoricalResultsUnavailableError`` unchanged; a
``None`` return means "not found" (mirrors ``GetDraw``/``GetIngestionRun``).
"""

from __future__ import annotations

from lottolab.application.historical_queries import (
    DEFAULT_PAGE_LIMIT,
    DEFAULT_PAGE_OFFSET,
    MAX_PAGE_LIMIT,
    MIN_PAGE_LIMIT,
    TICKET_COUNT_CHOICES,
    HistoricalPortfolioRecord,
    HistoricalReplayPage,
    HistoricalReplayQuery,
    HistoricalRunPage,
    HistoricalRunQuery,
    HistoricalStrategySummaryList,
    InvalidHistoricalQueryError,
)
from lottolab.application.ports import HistoricalResultQueryRepositoryFactory


def _validate_pagination(limit: int, offset: int) -> None:
    if not (MIN_PAGE_LIMIT <= limit <= MAX_PAGE_LIMIT):
        raise InvalidHistoricalQueryError(
            f"limit must be between {MIN_PAGE_LIMIT} and {MAX_PAGE_LIMIT}"
        )
    if offset < 0:
        raise InvalidHistoricalQueryError("offset must be non-negative")


def _validate_ticket_count(ticket_count: int) -> None:
    if ticket_count not in TICKET_COUNT_CHOICES:
        raise InvalidHistoricalQueryError("ticket_count must be one of 10, 15, or 20")


class ListHistoricalRuns:
    def __init__(self, repository_factory: HistoricalResultQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(
        self, *, limit: int = DEFAULT_PAGE_LIMIT, offset: int = DEFAULT_PAGE_OFFSET
    ) -> HistoricalRunPage:
        _validate_pagination(limit, offset)
        return self._repository_factory().list_runs(HistoricalRunQuery(limit=limit, offset=offset))


class ListHistoricalStrategies:
    def __init__(self, repository_factory: HistoricalResultQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, run_id: str, *, ticket_count: int) -> HistoricalStrategySummaryList | None:
        _validate_ticket_count(ticket_count)
        return self._repository_factory().list_strategies(run_id, ticket_count=ticket_count)


class ListHistoricalReplayPortfolios:
    def __init__(self, repository_factory: HistoricalResultQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(
        self,
        run_id: str,
        *,
        strategy_id: str,
        ticket_count: int,
        m4plus_only: bool = False,
        limit: int = DEFAULT_PAGE_LIMIT,
        offset: int = DEFAULT_PAGE_OFFSET,
    ) -> HistoricalReplayPage | None:
        _validate_ticket_count(ticket_count)
        _validate_pagination(limit, offset)
        query = HistoricalReplayQuery(
            strategy_id=strategy_id,
            ticket_count=ticket_count,
            m4plus_only=m4plus_only,
            limit=limit,
            offset=offset,
        )
        return self._repository_factory().list_replay_portfolios(run_id, query)


class GetHistoricalPortfolio:
    def __init__(self, repository_factory: HistoricalResultQueryRepositoryFactory) -> None:
        self._repository_factory = repository_factory

    def execute(self, portfolio_id: str, *, ticket_count: int) -> HistoricalPortfolioRecord | None:
        _validate_ticket_count(ticket_count)
        return self._repository_factory().get_portfolio(portfolio_id, ticket_count=ticket_count)
