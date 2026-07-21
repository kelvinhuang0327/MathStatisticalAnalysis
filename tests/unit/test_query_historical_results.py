"""Unit tests for the BLHQ R2 historical-results query use cases.

Each use case is exercised against a fake in-memory repository, never a real
SQLite database (see ``tests/integration/test_historical_query_repository.py``
for the real-database prefix/M4+/ordering proofs).
"""

from __future__ import annotations

import pytest

from lottolab.application.historical_queries import (
    HistoricalDrawIdentity,
    HistoricalPortfolioRecord,
    HistoricalReplayPage,
    HistoricalReplayQuery,
    HistoricalResultsUnavailableError,
    HistoricalRunPage,
    HistoricalRunQuery,
    HistoricalStrategySummaryList,
    InvalidHistoricalQueryError,
)
from lottolab.application.use_cases.query_historical_results import (
    GetHistoricalPortfolio,
    ListHistoricalReplayPortfolios,
    ListHistoricalRuns,
    ListHistoricalStrategies,
)


class _FakeQueryRepository:
    def __init__(
        self,
        *,
        run_page: HistoricalRunPage | None = None,
        strategies: HistoricalStrategySummaryList | None = None,
        replay_page: HistoricalReplayPage | None = None,
        portfolio: HistoricalPortfolioRecord | None = None,
        raise_unavailable: bool = False,
    ) -> None:
        self._run_page = run_page
        self._strategies = strategies
        self._replay_page = replay_page
        self._portfolio = portfolio
        self._raise_unavailable = raise_unavailable
        self.received_run_query: HistoricalRunQuery | None = None
        self.received_strategies_args: tuple[str, int] | None = None
        self.received_replay_query: tuple[str, HistoricalReplayQuery] | None = None
        self.received_portfolio_args: tuple[str, int] | None = None

    def list_runs(self, query: HistoricalRunQuery) -> HistoricalRunPage:
        if self._raise_unavailable:
            raise HistoricalResultsUnavailableError("unavailable")
        self.received_run_query = query
        assert self._run_page is not None
        return self._run_page

    def list_strategies(
        self, run_id: str, *, ticket_count: int
    ) -> HistoricalStrategySummaryList | None:
        if self._raise_unavailable:
            raise HistoricalResultsUnavailableError("unavailable")
        self.received_strategies_args = (run_id, ticket_count)
        return self._strategies

    def list_replay_portfolios(
        self, run_id: str, query: HistoricalReplayQuery
    ) -> HistoricalReplayPage | None:
        if self._raise_unavailable:
            raise HistoricalResultsUnavailableError("unavailable")
        self.received_replay_query = (run_id, query)
        return self._replay_page

    def get_portfolio(
        self, portfolio_id: str, *, ticket_count: int
    ) -> HistoricalPortfolioRecord | None:
        if self._raise_unavailable:
            raise HistoricalResultsUnavailableError("unavailable")
        self.received_portfolio_args = (portfolio_id, ticket_count)
        return self._portfolio


def _run_page() -> HistoricalRunPage:
    return HistoricalRunPage(items=(), total_count=0, limit=50, offset=0)


def _strategies() -> HistoricalStrategySummaryList:
    return HistoricalStrategySummaryList(run_id="run-1", ticket_count=10, items=())


def _replay_page() -> HistoricalReplayPage:
    return HistoricalReplayPage(
        run_id="run-1",
        strategy_id="strat-1",
        ticket_count=10,
        items=(),
        total_count=0,
        limit=50,
        offset=0,
    )


def _portfolio() -> HistoricalPortfolioRecord:
    draw = HistoricalDrawIdentity(
        draw_number="105",
        draw_date="2026-01-01",
        main_numbers=(1, 2, 3, 4, 5, 6),
        special_numbers=(7,),
        draw_sha256="a" * 64,
    )
    return HistoricalPortfolioRecord(
        portfolio_id="pf-1",
        run_id="run-1",
        strategy_snapshot_id="snap-1",
        strategy_id="strat-1",
        effective_strategy_id="strat-1",
        strategy_version="v1",
        replicate=1,
        constructor_identifier="c1",
        source_record_locator=None,
        portfolio_sha256="b" * 64,
        prefix10_sha256="c" * 64,
        prefix15_sha256="d" * 64,
        target_draw=draw,
        cutoff_draw=draw,
        requested_ticket_count=10,
        m4plus=False,
        tickets=(),
    )


# --- pagination validation ---


@pytest.mark.parametrize(("limit", "offset"), [(0, 0), (201, 0), (50, -1)])
def test_list_runs_rejects_invalid_pagination(limit: int, offset: int) -> None:
    repository = _FakeQueryRepository(run_page=_run_page())
    use_case = ListHistoricalRuns(lambda: repository)
    with pytest.raises(InvalidHistoricalQueryError):
        use_case.execute(limit=limit, offset=offset)


def test_list_runs_accepts_boundary_pagination() -> None:
    repository = _FakeQueryRepository(run_page=_run_page())
    use_case = ListHistoricalRuns(lambda: repository)
    use_case.execute(limit=1, offset=0)
    use_case.execute(limit=200, offset=0)
    assert repository.received_run_query == HistoricalRunQuery(limit=200, offset=0)


def test_list_replay_portfolios_rejects_invalid_pagination() -> None:
    repository = _FakeQueryRepository(replay_page=_replay_page())
    use_case = ListHistoricalReplayPortfolios(lambda: repository)
    with pytest.raises(InvalidHistoricalQueryError):
        use_case.execute("run-1", strategy_id="strat-1", ticket_count=10, limit=0, offset=0)
    with pytest.raises(InvalidHistoricalQueryError):
        use_case.execute("run-1", strategy_id="strat-1", ticket_count=10, limit=50, offset=-1)


# --- ticket_count validation ---


@pytest.mark.parametrize("ticket_count", [1, 5, 11, 25, 0, -10])
def test_list_strategies_rejects_invalid_ticket_count(ticket_count: int) -> None:
    repository = _FakeQueryRepository(strategies=_strategies())
    use_case = ListHistoricalStrategies(lambda: repository)
    with pytest.raises(InvalidHistoricalQueryError):
        use_case.execute("run-1", ticket_count=ticket_count)


@pytest.mark.parametrize("ticket_count", [10, 15, 20])
def test_list_strategies_accepts_each_valid_ticket_count(ticket_count: int) -> None:
    repository = _FakeQueryRepository(strategies=_strategies())
    use_case = ListHistoricalStrategies(lambda: repository)
    use_case.execute("run-1", ticket_count=ticket_count)
    assert repository.received_strategies_args == ("run-1", ticket_count)


def test_get_portfolio_rejects_invalid_ticket_count() -> None:
    repository = _FakeQueryRepository(portfolio=_portfolio())
    use_case = GetHistoricalPortfolio(lambda: repository)
    with pytest.raises(InvalidHistoricalQueryError):
        use_case.execute("pf-1", ticket_count=12)


def test_list_replay_portfolios_rejects_invalid_ticket_count() -> None:
    repository = _FakeQueryRepository(replay_page=_replay_page())
    use_case = ListHistoricalReplayPortfolios(lambda: repository)
    with pytest.raises(InvalidHistoricalQueryError):
        use_case.execute("run-1", strategy_id="strat-1", ticket_count=13, limit=50, offset=0)


# --- completed-only visibility / not-found mapping ---


def test_list_strategies_returns_none_when_run_not_found_or_not_completed() -> None:
    repository = _FakeQueryRepository(strategies=None)
    use_case = ListHistoricalStrategies(lambda: repository)
    assert use_case.execute("missing-run", ticket_count=10) is None


def test_list_replay_portfolios_returns_none_when_run_not_found_or_not_completed() -> None:
    repository = _FakeQueryRepository(replay_page=None)
    use_case = ListHistoricalReplayPortfolios(lambda: repository)
    assert (
        use_case.execute("missing-run", strategy_id="strat-1", ticket_count=10, limit=50, offset=0)
        is None
    )


def test_get_portfolio_returns_none_when_not_found() -> None:
    repository = _FakeQueryRepository(portfolio=None)
    use_case = GetHistoricalPortfolio(lambda: repository)
    assert use_case.execute("missing-portfolio", ticket_count=10) is None


# --- repository-unavailable mapping ---


def test_list_runs_propagates_repository_unavailable() -> None:
    repository = _FakeQueryRepository(raise_unavailable=True)
    use_case = ListHistoricalRuns(lambda: repository)
    with pytest.raises(HistoricalResultsUnavailableError):
        use_case.execute(limit=50, offset=0)


def test_list_strategies_propagates_repository_unavailable() -> None:
    repository = _FakeQueryRepository(raise_unavailable=True)
    use_case = ListHistoricalStrategies(lambda: repository)
    with pytest.raises(HistoricalResultsUnavailableError):
        use_case.execute("run-1", ticket_count=10)


def test_list_replay_portfolios_propagates_repository_unavailable() -> None:
    repository = _FakeQueryRepository(raise_unavailable=True)
    use_case = ListHistoricalReplayPortfolios(lambda: repository)
    with pytest.raises(HistoricalResultsUnavailableError):
        use_case.execute("run-1", strategy_id="strat-1", ticket_count=10, limit=50, offset=0)


def test_get_portfolio_propagates_repository_unavailable() -> None:
    repository = _FakeQueryRepository(raise_unavailable=True)
    use_case = GetHistoricalPortfolio(lambda: repository)
    with pytest.raises(HistoricalResultsUnavailableError):
        use_case.execute("pf-1", ticket_count=10)


# --- exact prefix selection / M4+ semantics: use case forwards params unchanged ---


def test_list_replay_portfolios_forwards_exact_prefix_and_m4plus_only_flag() -> None:
    repository = _FakeQueryRepository(replay_page=_replay_page())
    use_case = ListHistoricalReplayPortfolios(lambda: repository)
    use_case.execute(
        "run-1", strategy_id="strat-1", ticket_count=15, m4plus_only=True, limit=25, offset=5
    )
    assert repository.received_replay_query == (
        "run-1",
        HistoricalReplayQuery(
            strategy_id="strat-1", ticket_count=15, m4plus_only=True, limit=25, offset=5
        ),
    )


def test_get_portfolio_forwards_exact_requested_ticket_count() -> None:
    repository = _FakeQueryRepository(portfolio=_portfolio())
    use_case = GetHistoricalPortfolio(lambda: repository)
    use_case.execute("pf-1", ticket_count=20)
    assert repository.received_portfolio_args == ("pf-1", 20)
