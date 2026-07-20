"""Ports the application layer depends on; infrastructure provides implementations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from lottolab.application.draw_data import (
    DrawHistoryPage,
    DrawHistoryQuery,
    DrawRecord,
    ImportCommitResult,
    IngestionRunDetail,
    IngestionRunPage,
    IngestionRunQuery,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_results import HistoricalImportCommitResult, HistoricalRunImport
from lottolab.domain.ingestion import DrawCsvParseResult


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
