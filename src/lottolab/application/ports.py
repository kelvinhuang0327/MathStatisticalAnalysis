"""Ports the application layer depends on; infrastructure provides implementations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Protocol, runtime_checkable

from lottolab.application.biglotto_multi_ticket_records import (
    B649MultiTicketRecordDataset,
)
from lottolab.application.draw_automation import (
    IngestionAuditContext,
    ProviderFetchResult,
)
from lottolab.application.draw_data import (
    DrawHistoryPage,
    DrawHistoryQuery,
    DrawRecord,
    ImportCommitResult,
    IngestionRunDetail,
    IngestionRunPage,
    IngestionRunQuery,
)
from lottolab.application.historical_prefix_success_windows import (
    HistoricalPrefixSuccessWindowSource,
)
from lottolab.application.historical_queries import (
    HistoricalPortfolioRecord,
    HistoricalReplayPage,
    HistoricalReplayQuery,
    HistoricalRunPage,
    HistoricalRunQuery,
    HistoricalStrategySummaryList,
)
from lottolab.application.p638_historical import (
    P638RankingPage,
    P638ReplayPage,
    P638ReplayQuery,
    P638RunPage,
    P638StrategyMetrics,
    P638StrategyPage,
    P638TargetDetail,
)
from lottolab.application.strategy_evidence import StrategyEvidenceRegistrySnapshot
from lottolab.application.t539_historical import (
    T539CoverageLedger,
    T539RankingPage,
    T539ReplayPage,
    T539ReplayQuery,
    T539RunPage,
    T539StrategyMetrics,
    T539StrategyPage,
    T539TargetDetail,
)
from lottolab.domain.batch_imports import (
    BatchDrawImportCommit,
    BatchDrawImportPreview,
    ImportFilePayload,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_results import HistoricalImportCommitResult, HistoricalRunImport
from lottolab.domain.ingestion import DrawCsvParseResult
from lottolab.domain.ordered_candidate_materialization import (
    OrderedCandidateSourceSnapshot,
)
from lottolab.domain.prize_evaluation import PrizeEvaluationResult
from lottolab.domain.replay_history import ReplayCausalDrawRow
from lottolab.domain.replay_scoring import (
    ReplayTargetOutcomeReadResult,
)
from lottolab.domain.replay_scoring_projection import (
    ReplayOverallAggregateProjection,
    ReplayScoredPredictionProjection,
    ReplayScoringPersistResult,
    ReplayScoringRunProjection,
    ReplayStrategyAggregateProjection,
)
from lottolab.evidence.ordered_candidate_emission_package import (
    OrderedCandidateEmissionPackage,
)
from lottolab.evidence.replay_scoring_artifact import ReplayScoringArtifact


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


class BatchDrawImportRepository(Protocol):
    def apply_valid_batch_import(self, preview: BatchDrawImportPreview) -> BatchDrawImportCommit:
        """Atomically apply all accepted rows from one multi-file import."""
        ...


class BatchDrawImportParser(Protocol):
    def __call__(self, payloads: tuple[ImportFilePayload, ...]) -> BatchDrawImportPreview:
        """Parse one bounded batch without filesystem or database I/O."""
        ...


class DrawAutomationRepository(Protocol):
    def apply_automation_import(
        self,
        result: DrawCsvParseResult,
        context: IngestionAuditContext,
    ) -> ImportCommitResult:
        """Persist one provider fetch transaction and its append-only audit."""
        ...

    def record_automation_failure(
        self,
        context: IngestionAuditContext,
        *,
        error_code: str,
    ) -> None:
        """Append one sanitized failed automation audit without draw writes."""
        ...


class IngestionRunRepository(Protocol):
    def list_ingestion_runs(self, query: IngestionRunQuery) -> IngestionRunPage:
        """Return one deterministic ingestion-log page."""
        ...

    def get_ingestion_run(self, run_id: str) -> IngestionRunDetail | None:
        """Return a run plus bounded ordered item details."""
        ...


class DrawDataRepository(
    DrawRepository,
    DrawImportRepository,
    BatchDrawImportRepository,
    DrawAutomationRepository,
    IngestionRunRepository,
    Protocol,
):
    """Combined operation-scoped port implemented by local persistence."""


class DrawCsvParser(Protocol):
    def __call__(self, content: str | bytes, *, filename: str = "") -> DrawCsvParseResult: ...


type DrawDataRepositoryFactory = Callable[[], DrawDataRepository]
type DrawAutomationRepositoryFactory = Callable[[], DrawAutomationRepository]


@runtime_checkable
class B649MultiTicketRecordReader(Protocol):
    """Load the one checksum-pinned aggregate projection without side effects."""

    def read(self) -> B649MultiTicketRecordDataset:
        """Return the complete validated 221-strategy aggregate projection."""
        ...


type B649MultiTicketRecordReaderFactory = Callable[[], B649MultiTicketRecordReader]


@runtime_checkable
class DrawDataProvider(Protocol):
    @property
    def provider_id(self) -> str:
        """Stable provider identity stored in ingestion audit records."""
        ...

    @property
    def provider_version(self) -> str:
        """Stable provider contract version stored in ingestion audit records."""
        ...

    def fetch_draws(
        self,
        *,
        lottery_type: LotteryType,
        date_from: date,
        date_to: date,
    ) -> ProviderFetchResult:
        """Fetch one bounded inclusive range without writing application state."""
        ...


type DrawDataProviderFactory = Callable[[], DrawDataProvider | None]


@runtime_checkable
class StrategyEvidenceRegistryReader(Protocol):
    def read(self) -> StrategyEvidenceRegistrySnapshot:
        """Read only committed registry and definition state."""
        ...


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


class P638HistoricalQueryRepository(Protocol):
    """Read-only, POWER_LOTTO-scoped query port for the P638 V2 projection."""

    def list_runs(self, *, limit: int, offset: int) -> P638RunPage:
        """Return completed P638 forwarding runs, newest first."""
        ...

    def list_strategies(self, run_id: str, *, limit: int, offset: int) -> P638StrategyPage | None:
        """Return the complete current P638 ledger for one completed run."""
        ...

    def list_replay(self, run_id: str, query: P638ReplayQuery) -> P638ReplayPage | None:
        """Return paginated targets and their tickets for one completed run."""
        ...

    def get_target(self, run_id: str, target_id: str) -> P638TargetDetail | None:
        """Return one target and its ordered tickets, or ``None``."""
        ...

    def get_metrics(
        self, run_id: str, *, strategy_id: str | None = None
    ) -> P638StrategyMetrics | None:
        """Return server-side target, ticket, and hit distributions."""
        ...


type P638HistoricalQueryRepositoryFactory = Callable[[], P638HistoricalQueryRepository]


class P638All10RankingQueryRepository(Protocol):
    """Read-only, POWER_LOTTO-scoped query port for the all-10 prize-ranking projection.

    Distinct from :class:`P638HistoricalQueryRepository`: that port reads the
    frozen 8-strategy P638 Historical Results V2 projection, never mutated by
    this port's data. This port reads the separate all-10 executable-strategy
    official-prize ranking projection.
    """

    def list_rankings(self, run_id: str) -> P638RankingPage | None:
        """Return exactly 10 ranking rows for one completed run, or ``None``."""
        ...


type P638All10RankingQueryRepositoryFactory = Callable[[], P638All10RankingQueryRepository]


class T539HistoricalQueryRepository(Protocol):
    """Read-only, DAILY_539-scoped query port over the sealed T539 Wave 1 run.

    Unlike the P638 verticals, T539 Wave 1 has no forwarding step and no
    separate ranking projection: this single port reads directly from the
    frozen Wave 1 database's own flat schema, including the static coverage
    ledger (executed and blocked strategy identities).
    """

    def list_runs(self, *, limit: int, offset: int) -> T539RunPage:
        """Return the sealed Wave 1 run(s), newest first."""
        ...

    def list_strategies(self, run_id: str, *, limit: int, offset: int) -> T539StrategyPage | None:
        """Return the eight executed strategies for one run, or ``None``."""
        ...

    def list_replay(self, run_id: str, query: T539ReplayQuery) -> T539ReplayPage | None:
        """Return paginated targets and their tickets for one run, or ``None``."""
        ...

    def get_target(self, run_id: str, target_id: str) -> T539TargetDetail | None:
        """Return one target and its ordered tickets, or ``None``."""
        ...

    def get_metrics(
        self, run_id: str, *, strategy_id: str | None = None
    ) -> T539StrategyMetrics | None:
        """Return server-side target, ticket, and hit distributions."""
        ...

    def list_rankings(self, run_id: str) -> T539RankingPage | None:
        """Return exactly 8 official-prize ranking rows, or ``None``."""
        ...

    def get_coverage_ledger(self, run_id: str) -> T539CoverageLedger | None:
        """Return the complete Wave 1 coverage ledger, or ``None``."""
        ...


type T539HistoricalQueryRepositoryFactory = Callable[[], T539HistoricalQueryRepository]


@runtime_checkable
class HistoricalPrefixSuccessWindowSourceReader(Protocol):
    """Narrow read-only boundary for one exact persisted Historical Prefix source."""

    def load_source(
        self, import_identity_sha256: str
    ) -> HistoricalPrefixSuccessWindowSource | None:
        """Return one exact COMPLETED source, or ``None`` when it is absent."""
        ...


type HistoricalPrefixSuccessWindowSourceReaderFactory = Callable[
    [], HistoricalPrefixSuccessWindowSourceReader
]


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


class ReplayScoringProjectionWriter(Protocol):
    """Narrow, transactional writer for one whole Replay-scoring run."""

    def persist_replay_scoring_artifact(
        self,
        artifact: ReplayScoringArtifact,
        canonical_bytes: bytes,
    ) -> ReplayScoringPersistResult:
        """Persist one already-validated artifact transactionally, or fail closed.

        Returns ``INSERTED`` for a fresh run, ``ALREADY_PRESENT`` for an exact
        idempotent re-import (identical ``canonical_bytes``), or ``CONFLICT``
        when the same run identity already exists with different content —
        never overwriting, merging, or partially persisting a run.
        """
        ...


class ReplayScoringProjectionReader(Protocol):
    """Narrow, read-only boundary over the persisted Replay-scoring projection.

    Every method treats an absent run as ``None`` rather than raising. Reads
    never mutate storage.
    """

    def get_run(self, scoring_artifact_payload_sha256: str) -> ReplayScoringRunProjection | None:
        """Return the stored run identity, or ``None`` if not found."""
        ...

    def get_replay_scoring_artifact(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayScoringArtifact | None:
        """Reconstruct the exact original typed artifact, or ``None`` if not found."""
        ...

    def list_scored_predictions(
        self,
        scoring_artifact_payload_sha256: str,
        *,
        target_draw_number: str | None = None,
        strategy_id: str | None = None,
    ) -> tuple[ReplayScoredPredictionProjection, ...]:
        """Return scored records in stored ordinal order, optionally filtered."""
        ...

    def list_strategy_aggregates(
        self, scoring_artifact_payload_sha256: str
    ) -> tuple[ReplayStrategyAggregateProjection, ...]:
        """Return per-strategy aggregates in stored ordinal order."""
        ...

    def get_overall_aggregate(
        self, scoring_artifact_payload_sha256: str
    ) -> ReplayOverallAggregateProjection | None:
        """Return the run's single overall aggregate, or ``None`` if not found."""
        ...


type ReplayScoringProjectionReaderFactory = Callable[[], ReplayScoringProjectionReader]


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


@runtime_checkable
class OrderedCandidateMaterializationReader(Protocol):
    """Read-only boundary for one complete ordered-candidate source snapshot."""

    def read_source_snapshot(
        self,
        lottery_type: LotteryType,
    ) -> OrderedCandidateSourceSnapshot:
        """Return all source rows plus their exact LCJ-1 content digest."""
        ...


@runtime_checkable
class OrderedCandidatePackageWriter(Protocol):
    """Atomic absent-root seal boundary for one prevalidated package."""

    def write_package(
        self,
        output_directory: Path,
        package: OrderedCandidateEmissionPackage,
    ) -> None:
        """Seal the package without overwriting any existing path."""
        ...


type OrderedCandidateMaterializationReaderFactory = Callable[
    [], OrderedCandidateMaterializationReader
]
type OrderedCandidatePackageWriterFactory = Callable[[], OrderedCandidatePackageWriter]


@runtime_checkable
class LotteryPrizeEvaluator(Protocol):
    """Official prize-tier evaluation dispatched by lottery type.

    Each lottery type owns its distinct prize rules; this port never applies
    one lottery's hit signature to another's tiers.
    """

    def evaluate(
        self,
        *,
        lottery_type: LotteryType,
        predicted_main_numbers: tuple[int, ...],
        predicted_special_number: int | None,
        winning_main_numbers: tuple[int, ...],
        winning_special_number: int | None,
    ) -> PrizeEvaluationResult:
        """Score one ticket against one draw under that lottery's official rules."""
        ...
