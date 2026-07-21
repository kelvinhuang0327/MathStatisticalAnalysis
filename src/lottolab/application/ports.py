"""Ports the application layer depends on; infrastructure provides implementations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from lottolab.application.draw_data import (
    DrawHistoryPage,
    DrawHistoryQuery,
    DrawRecord,
    ImportCommitResult,
    IngestionRunDetail,
    IngestionRunPage,
    IngestionRunQuery,
)
from lottolab.application.historical_queries import (
    HistoricalPortfolioRecord,
    HistoricalReplayPage,
    HistoricalReplayQuery,
    HistoricalRunPage,
    HistoricalRunQuery,
    HistoricalStrategySummaryList,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_results import HistoricalImportCommitResult, HistoricalRunImport
from lottolab.domain.ingestion import DrawCsvParseResult
from lottolab.domain.replay_history import ReplayCausalDrawRow
from lottolab.domain.replay_scoring import (
    ReplayTargetOutcomeReadResult,
)


class DrawRepository(Protocol):
    def list_draws(self, query: DrawHistoryQuery) -> DrawHistoryPage:
        """Return one deterministic draw-history page."""
        ...

    def get_draw(self, lottery_type: LotteryType, draw_number: str) -> DrawRecord | None:
        """Return one draw identity without exposing storage rows."""
        ...


class DrawImportRepository(Protocol):
    def apply_valid_import(self, result: DrawCsvParseResult) -> ImportCommitResult:
        """Atomically apply a fully valid canonical parse result."""
        ...


class IngestionRunRepository(Protocol):
    def list_ingestion_runs(self, query: IngestionRunQuery) -> IngestionRunPage:
        """Return one deterministic ingestion-log page."""
        ...

    def get_ingestion_run(self, run_id: str) -> IngestionRunDetail | None:
        """Return a run plus bounded ordered item details."""
        ...


class DrawDataRepository(DrawRepository, DrawImportRepository, IngestionRunRepository, Protocol):
    """Combined operation-scoped port implemented by local persistence."""


class DrawCsvParser(Protocol):
    def __call__(self, content: str | bytes, *, filename: str = "") -> DrawCsvParseResult: ...


type DrawDataRepositoryFactory = Callable[[], DrawDataRepository]


class HistoricalResultRepository(Protocol):
    def commit_import(self, run_import: HistoricalRunImport) -> HistoricalImportCommitResult:
        """Atomically commit one validated historical import.

        Returns the existing COMPLETED result as an idempotent no-op when a run
        with the same ``import_identity_sha256`` already completed; otherwise
        commits a fresh COMPLETED run, or, on a mid-transaction persistence
        failure, records a FAILED audit run with zero child rows and returns
        that FAILED result.
        """
        ...


class HistoricalResultQueryRepository(Protocol):
    """Read-only query port over the already-committed historical-results projection.

    Distinct from ``HistoricalResultRepository`` (write-side ``commit_import``):
    this port never mutates storage. Every method treats a run whose
    ``status`` is not ``COMPLETED`` as though it does not exist.
    """

    def list_runs(self, query: HistoricalRunQuery) -> HistoricalRunPage:
        """Return one deterministic page of COMPLETED runs, newest first."""
        ...

    def list_strategies(
        self, run_id: str, *, ticket_count: int
    ) -> HistoricalStrategySummaryList | None:
        """Return per-strategy summaries for a COMPLETED run, or None if not found."""
        ...

    def list_replay_portfolios(
        self, run_id: str, query: HistoricalReplayQuery
    ) -> HistoricalReplayPage | None:
        """Return one page of portfolios for a COMPLETED run, or None if not found."""
        ...

    def get_portfolio(
        self, portfolio_id: str, *, ticket_count: int
    ) -> HistoricalPortfolioRecord | None:
        """Return one portfolio's committed detail, or None if not found."""
        ...


type HistoricalResultQueryRepositoryFactory = Callable[[], HistoricalResultQueryRepository]


class TargetDrawNotFoundError(LookupError):
    """No draw matches ``(lottery_type, target_draw_number)`` exactly."""


@runtime_checkable
class DrawHistoryReader(Protocol):
    """Replay's narrow, read-only causal Big Lotto history boundary.

    Returns/raises in terms of domain types only — never sqlite3 rows, SQL
    strings, or any UI/HTTP concept.
    """

    def read_causal_history(
        self,
        lottery_type: LotteryType,
        target_draw_number: str,
        *,
        maximum_history_draws: int | None = None,
    ) -> tuple[ReplayCausalDrawRow, ...]:
        """Return draws strictly before ``target_draw_number``, ascending.

        Ordering is by ``draw_date`` then by the numeric ``draw_number`` —
        never lexicographic (see :attr:`lottolab.domain.draws.Draw.sort_key`
        for why). When ``maximum_history_draws`` is given, only the most
        recent N draws before the target are returned (still ascending).
        Raises :class:`TargetDrawNotFoundError` when the target does not
        exist for ``lottery_type``.
        """
        ...


type DrawHistoryReaderFactory = Callable[[], DrawHistoryReader]


@runtime_checkable
class ReplayTargetOutcomeReader(Protocol):
    """Narrow, read-only boundary for one exact Replay target outcome."""

    def load_target_outcome(
        self,
        lottery_type: LotteryType,
        target_draw_number: str,
    ) -> ReplayTargetOutcomeReadResult:
        """Return a typed found/not-found result without leaking storage errors."""
        ...
