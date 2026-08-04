"""Deterministic, resumable BIG_LOTTO historical-backtest application runner."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from threading import Event
from typing import Protocol, cast

from lottolab.application.research_store import (
    ClosureInput,
    CompletedTargetCursor,
    DrawBindingInput,
    ResearchStore,
    RunProgress,
    RunSummaryInput,
    StrategySnapshotInput,
    TargetCommitInput,
    TicketInput,
    TicketResultInput,
)
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetStatus,
    GeneratePortfolioStatus,
)
from lottolab.application.use_cases.generate_ordered_candidate_emission import (
    GenerateOrderedCandidateEmission,
    GenerateOrderedCandidateEmissionInput,
    GenerateOrderedPortfolioEmission,
    GenerateOrderedPortfolioEmissionInput,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    BigLottoPrizeTier,
    resolve_big_lotto_prize_tier,
    score_big_lotto_ticket,
)
from lottolab.domain.ordered_candidate_materialization import (
    OrderedCandidateSourceRow,
    OrderedCandidateSourceSnapshot,
)
from lottolab.domain.research import (
    ResearchExecutionStatus,
    ResearchRunKind,
    ResearchRunStatus,
    StrategyProvenanceAvailability,
)
from lottolab.domain.strategies import ResponseShape
from lottolab.evidence.canonical_json import (
    CanonicalizationError,
    canonical_bytes,
    canonical_file_bytes,
    loads_canonical,
    sha256_hex,
)
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.catalog import (
    StrategyCatalog,
    UnknownStrategyError,
)
from lottolab.strategies.executable_registry import (
    ExecutableRegistry,
    NotExecutableError,
)

BIG_LOTTO_RESEARCH_BACKTEST_RUN_MANIFEST_V1 = (
    "BIG_LOTTO_RESEARCH_BACKTEST_RUN_MANIFEST_V1"
)
RESEARCH_BACKTEST_RUNNER_VERSION = "1.0.0"
RESEARCH_BACKTEST_PROGRESS_SCHEMA_VERSION = (
    "BIG_LOTTO_RESEARCH_BACKTEST_PROGRESS_V1"
)
RESEARCH_BACKTEST_SUMMARY_VERSION = 1
RESEARCH_BACKTEST_PRODUCER_IDENTITY = (
    "lottolab.application.research_backtest_runner"
)
RESEARCH_BACKTEST_SEED_PROTOCOL = (
    "DETERMINISTIC_HISTORY_ONLY_NO_RANDOM_SEED_V1"
)
RESEARCH_BACKTEST_SOURCE_HISTORY_ORDER = (
    "draw_date_then_numeric_draw_number_ascending"
)
RESEARCH_BACKTEST_SCORING_SEMANTICS = "VERSIONED_CURRENT_SCORER"

_MANIFEST_KEYS = {
    "dataset_id",
    "dataset_version",
    "expected_source_snapshot_sha256",
    "lottery_type",
    "maximum_history_draws",
    "minimum_history_draws",
    "replicate",
    "run_kind",
    "schema_version",
    "strategy_ids",
    "target_draws",
}
_ASCII_DECIMAL = re.compile(r"[0-9]+", flags=re.ASCII)
_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_COMMIT_OID = re.compile(r"[0-9a-f]{40}", flags=re.ASCII)
_STRATEGY_ID = re.compile(r"[a-z0-9][a-z0-9_]{0,127}", flags=re.ASCII)


class ResearchBacktestError(RuntimeError):
    """Base class for caller-safe runner failures."""


class ResearchBacktestInputError(ResearchBacktestError):
    """The complete manifest or its source binding is invalid."""

    def __init__(
        self,
        reason_code: str,
        detail: str,
        *,
        target_draw: str | None = None,
    ) -> None:
        self.reason_code = reason_code
        self.target_draw = target_draw
        super().__init__(detail)


class ResearchBacktestSourceError(ResearchBacktestError):
    """The pinned source snapshot cannot be used safely."""


class ResearchBacktestProvenanceError(ResearchBacktestError):
    """Native strategy or runner provenance cannot be represented honestly."""


class ResearchBacktestConflictError(ResearchBacktestError):
    """Stored immutable state conflicts with the deterministic run."""


class ResearchBacktestRunStateError(ResearchBacktestError):
    """The stored event-sourced run state cannot be resumed safely."""


class BigLottoSourceSnapshotReader(Protocol):
    """Application-owned read port for one checksum-pinned draw snapshot."""

    def read_source_snapshot(
        self,
        lottery_type: LotteryType,
    ) -> OrderedCandidateSourceSnapshot: ...


@dataclass(frozen=True, slots=True)
class StrategySourceIdentity:
    """Exact source bytes and versioned runtime identity for one native adapter."""

    strategy_source_sha256: str
    runtime_fingerprint: str

    def __post_init__(self) -> None:
        if _SHA256.fullmatch(self.strategy_source_sha256) is None:
            raise ValueError("strategy_source_sha256 must be a lowercase SHA-256")
        _require_canonical_json(self.runtime_fingerprint, "runtime_fingerprint")


class StrategySourceIdentityResolver(Protocol):
    """Outer-layer port for hashing the adapter module that the registry resolved."""

    def resolve(
        self,
        *,
        strategy_id: str,
        loaded_adapter: type[object],
    ) -> StrategySourceIdentity: ...


@dataclass(frozen=True, slots=True)
class BigLottoResearchBacktestManifest:
    """Canonical caller-ordered R1 execution manifest."""

    schema_version: str
    lottery_type: LotteryType
    run_kind: ResearchRunKind
    dataset_id: str
    dataset_version: str
    expected_source_snapshot_sha256: str
    target_draws: tuple[str, ...]
    strategy_ids: tuple[str, ...]
    minimum_history_draws: int
    maximum_history_draws: int
    replicate: int

    def __post_init__(self) -> None:
        if self.schema_version != BIG_LOTTO_RESEARCH_BACKTEST_RUN_MANIFEST_V1:
            raise ResearchBacktestInputError(
                "INVALID_MANIFEST_SCHEMA_VERSION",
                "manifest schema_version is unsupported",
            )
        if self.lottery_type is not LotteryType.BIG_LOTTO:
            raise ResearchBacktestInputError(
                "UNSUPPORTED_LOTTERY_TYPE",
                "manifest lottery_type must be BIG_LOTTO",
            )
        if self.run_kind is not ResearchRunKind.HISTORICAL_BACKTEST:
            raise ResearchBacktestInputError(
                "UNSUPPORTED_RUN_KIND",
                "manifest run_kind must be HISTORICAL_BACKTEST",
            )
        for value, name in (
            (self.dataset_id, "dataset_id"),
            (self.dataset_version, "dataset_version"),
        ):
            if (
                type(value) is not str
                or not value
                or value != value.strip()
            ):
                raise ResearchBacktestInputError(
                    f"INVALID_{name.upper()}",
                    f"manifest {name} must be a non-empty canonical string",
                )
        if _SHA256.fullmatch(self.expected_source_snapshot_sha256) is None:
            raise ResearchBacktestInputError(
                "INVALID_SOURCE_SNAPSHOT_SHA256",
                "manifest expected_source_snapshot_sha256 is invalid",
            )
        if not self.target_draws or any(
            type(draw) is not str or _ASCII_DECIMAL.fullmatch(draw) is None
            for draw in self.target_draws
        ):
            raise ResearchBacktestInputError(
                "INVALID_TARGET_DRAW",
                "manifest target_draws must contain ASCII decimal identities",
            )
        if len(set(self.target_draws)) != len(self.target_draws):
            raise ResearchBacktestInputError(
                "DUPLICATE_TARGET_DRAW",
                "manifest target_draws must not contain duplicates",
            )
        if not self.strategy_ids or any(
            type(strategy_id) is not str
            or _STRATEGY_ID.fullmatch(strategy_id) is None
            for strategy_id in self.strategy_ids
        ):
            raise ResearchBacktestInputError(
                "INVALID_STRATEGY_ID",
                "manifest strategy_ids must contain canonical strategy identities",
            )
        if len(set(self.strategy_ids)) != len(self.strategy_ids):
            raise ResearchBacktestInputError(
                "DUPLICATE_STRATEGY_ID",
                "manifest strategy_ids must not contain duplicates",
            )
        if (
            type(self.minimum_history_draws) is not int
            or self.minimum_history_draws <= 0
            or type(self.maximum_history_draws) is not int
            or self.maximum_history_draws <= 0
        ):
            raise ResearchBacktestInputError(
                "INVALID_HISTORY_BOUNDS",
                "manifest history bounds must be positive integers",
            )
        if self.minimum_history_draws > self.maximum_history_draws:
            raise ResearchBacktestInputError(
                "INVALID_HISTORY_BOUNDS",
                "manifest minimum_history_draws must not exceed maximum_history_draws",
            )
        if type(self.replicate) is not int or self.replicate != 1:
            raise ResearchBacktestInputError(
                "INVALID_REPLICATE",
                "manifest replicate must be exactly 1",
            )

    @classmethod
    def from_canonical_file_bytes(
        cls,
        raw: bytes,
    ) -> BigLottoResearchBacktestManifest:
        """Parse exactly one LCJ-1 file encoding, including its trailing LF."""

        if type(raw) is not bytes:
            raise ResearchBacktestInputError(
                "INVALID_MANIFEST_BYTES",
                "manifest file must contain exact bytes",
            )
        try:
            decoded = loads_canonical(raw)
        except CanonicalizationError as exc:
            raise ResearchBacktestInputError(
                "INVALID_MANIFEST_JSON",
                "manifest file is not valid canonical JSON",
            ) from exc
        if not isinstance(decoded, dict):
            raise ResearchBacktestInputError(
                "INVALID_MANIFEST_SHAPE",
                "manifest must be one canonical JSON object",
            )
        document = cast(dict[str, object], decoded)
        if set(document) != _MANIFEST_KEYS:
            raise ResearchBacktestInputError(
                "INVALID_MANIFEST_FIELDS",
                "manifest fields do not match the R1 contract",
            )
        try:
            expected_bytes = canonical_file_bytes(document)
        except CanonicalizationError as exc:  # pragma: no cover - loads already checked
            raise ResearchBacktestInputError(
                "INVALID_MANIFEST_JSON",
                "manifest file is not valid canonical JSON",
            ) from exc
        if raw != expected_bytes:
            raise ResearchBacktestInputError(
                "NON_CANONICAL_MANIFEST_JSON",
                "manifest file must use the canonical JSON encoding",
            )
        return cls(
            schema_version=_required_string(document, "schema_version"),
            lottery_type=_enum_value(
                LotteryType,
                document,
                "lottery_type",
                "UNSUPPORTED_LOTTERY_TYPE",
            ),
            run_kind=_enum_value(
                ResearchRunKind,
                document,
                "run_kind",
                "UNSUPPORTED_RUN_KIND",
            ),
            dataset_id=_required_string(document, "dataset_id"),
            dataset_version=_required_string(document, "dataset_version"),
            expected_source_snapshot_sha256=_required_string(
                document,
                "expected_source_snapshot_sha256",
            ),
            target_draws=_required_string_tuple(document, "target_draws"),
            strategy_ids=_required_string_tuple(document, "strategy_ids"),
            minimum_history_draws=_required_int(
                document,
                "minimum_history_draws",
            ),
            maximum_history_draws=_required_int(
                document,
                "maximum_history_draws",
            ),
            replicate=_required_int(document, "replicate"),
        )

    def canonical_dict(self) -> dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "expected_source_snapshot_sha256": (
                self.expected_source_snapshot_sha256
            ),
            "lottery_type": self.lottery_type.value,
            "maximum_history_draws": self.maximum_history_draws,
            "minimum_history_draws": self.minimum_history_draws,
            "replicate": self.replicate,
            "run_kind": self.run_kind.value,
            "schema_version": self.schema_version,
            "strategy_ids": list(self.strategy_ids),
            "target_draws": list(self.target_draws),
        }

    def canonical_file_bytes(self) -> bytes:
        return canonical_file_bytes(self.canonical_dict())

    @property
    def manifest_sha256(self) -> str:
        return sha256_hex(canonical_bytes(self.canonical_dict()))


@dataclass(frozen=True, slots=True)
class RunBigLottoResearchBacktestResult:
    """Structured terminal or safely paused result."""

    run_id: str
    status: ResearchRunStatus
    manifest_sha256: str
    source_snapshot_sha256: str
    expected_target_count: int
    completed_target_count: int
    targets_created: int
    tickets_created: int
    results_created: int
    status_counts: tuple[tuple[ResearchExecutionStatus, int], ...]
    idempotent_no_op: bool
    interrupted: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "completed_target_count": self.completed_target_count,
            "expected_target_count": self.expected_target_count,
            "idempotent_no_op": self.idempotent_no_op,
            "interrupted": self.interrupted,
            "manifest_sha256": self.manifest_sha256,
            "results_created": self.results_created,
            "run_id": self.run_id,
            "source_snapshot_sha256": self.source_snapshot_sha256,
            "status": self.status.value,
            "status_counts": {
                status.value: count for status, count in self.status_counts
            },
            "targets_created": self.targets_created,
            "tickets_created": self.tickets_created,
        }


@dataclass(frozen=True, slots=True)
class _PreparedStrategy:
    strategy_id: str
    strategy_name: str
    strategy_version: str
    lifecycle_status: str
    governance_status: str
    source_identity: StrategySourceIdentity
    snapshot_id: str
    response_shape: ResponseShape


@dataclass(frozen=True, slots=True)
class _PreparedTarget:
    row: OrderedCandidateSourceRow
    bounded_history: tuple[OrderedCandidateSourceRow, ...]


@dataclass(frozen=True, slots=True)
class _PreparedRun:
    manifest: BigLottoResearchBacktestManifest
    snapshot: OrderedCandidateSourceSnapshot
    source_commit_oid: str
    strategies: tuple[_PreparedStrategy, ...]
    targets: tuple[_PreparedTarget, ...]
    run_id: str
    scoring_version: str


@dataclass(frozen=True, slots=True)
class _AttemptCommit:
    value: TargetCommitInput
    status: ResearchExecutionStatus
    ticket_count: int
    result_count: int


class _ProgressCounts:
    """Mutable in-memory counters sealed into each pause/completion cursor."""

    def __init__(
        self,
        strategy_ids: tuple[str, ...],
        *,
        status_counts: Mapping[ResearchExecutionStatus, int] | None = None,
        strategy_status_counts: (
            Mapping[str, Mapping[ResearchExecutionStatus, int]] | None
        ) = None,
    ) -> None:
        self.status_counts: Counter[ResearchExecutionStatus] = Counter(
            status_counts or {}
        )
        self.strategy_status_counts: dict[
            str,
            Counter[ResearchExecutionStatus],
        ] = {
            strategy_id: Counter(
                {}
                if strategy_status_counts is None
                else strategy_status_counts.get(strategy_id, {})
            )
            for strategy_id in strategy_ids
        }

    @property
    def completed_target_count(self) -> int:
        return sum(self.status_counts.values())

    def record(
        self,
        strategy_id: str,
        status: ResearchExecutionStatus,
    ) -> None:
        self.status_counts[status] += 1
        self.strategy_status_counts[strategy_id][status] += 1


class RunBigLottoResearchBacktest:
    """Validate completely, then execute and persist one target transaction at a time."""

    def __init__(
        self,
        *,
        repository_factory: Callable[[], ResearchStore],
        source_reader: BigLottoSourceSnapshotReader,
        catalog: StrategyCatalog,
        executable_registry: ExecutableRegistry,
        generate_ordered_candidate_emission: GenerateOrderedCandidateEmission,
        generate_ordered_portfolio_emission: GenerateOrderedPortfolioEmission,
        source_commit_resolver: Callable[[], str],
        strategy_source_identity_resolver: StrategySourceIdentityResolver,
    ) -> None:
        self._repository_factory = repository_factory
        self._source_reader = source_reader
        self._catalog = catalog
        self._registry = executable_registry
        self._generate = generate_ordered_candidate_emission
        self._generate_portfolio = generate_ordered_portfolio_emission
        self._source_commit_resolver = source_commit_resolver
        self._strategy_source_identity_resolver = (
            strategy_source_identity_resolver
        )

    def execute(
        self,
        manifest: BigLottoResearchBacktestManifest,
        *,
        stop_requested: Event | None = None,
    ) -> RunBigLottoResearchBacktestResult:
        prepared = self._prepare(manifest)
        repository = self._repository_factory()
        return self._execute_prepared(
            repository,
            prepared,
            stop_requested=stop_requested,
        )

    def deterministic_run_id(
        self,
        manifest: BigLottoResearchBacktestManifest,
    ) -> str:
        """Resolve the stable run identity after every pre-write validation."""

        return self._prepare(manifest).run_id

    def _prepare(
        self,
        manifest: BigLottoResearchBacktestManifest,
    ) -> _PreparedRun:
        if type(manifest) is not BigLottoResearchBacktestManifest:
            raise ResearchBacktestInputError(
                "INVALID_MANIFEST_TYPE",
                "runner requires a typed R1 manifest",
            )
        try:
            snapshot = self._source_reader.read_source_snapshot(
                LotteryType.BIG_LOTTO
            )
        except ResearchBacktestError:
            raise
        except Exception as exc:
            raise ResearchBacktestSourceError(
                "source snapshot could not be read safely"
            ) from exc
        if (
            snapshot.source_snapshot_sha256
            != manifest.expected_source_snapshot_sha256
        ):
            raise ResearchBacktestInputError(
                "SOURCE_SNAPSHOT_SHA256_MISMATCH",
                "source snapshot SHA-256 does not match the manifest",
            )

        target_index_by_draw = {
            row.draw_number: index for index, row in enumerate(snapshot.rows)
        }
        targets: list[_PreparedTarget] = []
        for target_draw in manifest.target_draws:
            target_index = target_index_by_draw.get(target_draw)
            if target_index is None:
                raise ResearchBacktestInputError(
                    "TARGET_DRAW_NOT_FOUND",
                    f"target draw {target_draw} does not exist in the pinned source snapshot",
                    target_draw=target_draw,
                )
            earlier_rows = snapshot.rows[:target_index]
            if not earlier_rows:
                raise ResearchBacktestInputError(
                    "TARGET_HAS_NO_STRICTLY_EARLIER_HISTORY",
                    f"target draw {target_draw} has no strictly earlier source row",
                    target_draw=target_draw,
                )
            bounded_history = earlier_rows[-manifest.maximum_history_draws :]
            if not bounded_history:  # pragma: no cover - guarded above and max > 0
                raise ResearchBacktestInputError(
                    "TARGET_HAS_NO_STRICTLY_EARLIER_HISTORY",
                    f"target draw {target_draw} has no strictly earlier source row",
                    target_draw=target_draw,
                )
            targets.append(
                _PreparedTarget(
                    row=snapshot.rows[target_index],
                    bounded_history=bounded_history,
                )
            )

        provisional_strategies: list[
            tuple[str, str, str, str, str, StrategySourceIdentity, ResponseShape]
        ] = []
        executable_ids = self._registry.executable_ids()
        for strategy_id in manifest.strategy_ids:
            try:
                descriptor = self._catalog.get(strategy_id)
            except UnknownStrategyError as exc:
                raise ResearchBacktestInputError(
                    "UNKNOWN_STRATEGY",
                    f"strategy {strategy_id} is not in the production catalog",
                ) from exc
            if (
                not descriptor.executable
                or strategy_id not in executable_ids
                or descriptor.adapter_path is None
            ):
                raise ResearchBacktestInputError(
                    "STRATEGY_NOT_EXECUTABLE",
                    f"strategy {strategy_id} is not currently executable",
                )
            if LotteryType.BIG_LOTTO not in descriptor.lottery_types:
                raise ResearchBacktestInputError(
                    "STRATEGY_NOT_BIG_LOTTO_COMPATIBLE",
                    f"strategy {strategy_id} is not BIG_LOTTO-compatible",
                )
            try:
                loaded_adapter = self._registry.load_adapter(strategy_id)
            except (NotExecutableError, UnknownStrategyError) as exc:
                raise ResearchBacktestInputError(
                    "STRATEGY_NOT_EXECUTABLE",
                    f"strategy {strategy_id} is not currently executable",
                ) from exc
            if not isinstance(loaded_adapter, type):
                raise ResearchBacktestProvenanceError(
                    f"native adapter identity is invalid for strategy {strategy_id}"
                )
            try:
                source_identity = (
                    self._strategy_source_identity_resolver.resolve(
                        strategy_id=strategy_id,
                        loaded_adapter=loaded_adapter,
                    )
                )
            except ResearchBacktestError:
                raise
            except Exception as exc:
                raise ResearchBacktestProvenanceError(
                    f"native source identity is unavailable for strategy {strategy_id}"
                ) from exc
            provisional_strategies.append(
                (
                    descriptor.strategy_id,
                    descriptor.strategy_name,
                    descriptor.version,
                    descriptor.lifecycle_status.value,
                    _governance_status(descriptor.provenance),
                    source_identity,
                    descriptor.response_shape,
                )
            )

        try:
            source_commit_oid = self._source_commit_resolver()
        except ResearchBacktestError:
            raise
        except Exception as exc:
            raise ResearchBacktestProvenanceError(
                "runner source commit could not be resolved"
            ) from exc
        if _COMMIT_OID.fullmatch(source_commit_oid) is None:
            raise ResearchBacktestProvenanceError(
                "runner source commit must be a lowercase Git SHA-1"
            )

        scoring_version = _scoring_version()
        run_identity = {
            "dataset_id": manifest.dataset_id,
            "dataset_version": manifest.dataset_version,
            "manifest_sha256": manifest.manifest_sha256,
            "rule_contract_version": BIG_LOTTO_RULE_CONTRACT.contract_version,
            "runner_source_commit_oid": source_commit_oid,
            "runner_version": RESEARCH_BACKTEST_RUNNER_VERSION,
            "scoring_version": scoring_version,
            "source_snapshot_sha256": snapshot.source_snapshot_sha256,
            "strategy_source_identities": [
                {
                    "runtime_fingerprint": source.runtime_fingerprint,
                    "strategy_id": strategy_id,
                    "strategy_source_sha256": source.strategy_source_sha256,
                    "strategy_version": strategy_version,
                }
                for (
                    strategy_id,
                    _strategy_name,
                    strategy_version,
                    _lifecycle_status,
                    _governance,
                    source,
                    _response_shape,
                ) in provisional_strategies
            ],
        }
        run_id = f"run-biglotto-backtest-{_canonical_sha256(run_identity)}"
        strategies = tuple(
            _PreparedStrategy(
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                strategy_version=strategy_version,
                lifecycle_status=lifecycle_status,
                governance_status=governance_status,
                source_identity=source_identity,
                snapshot_id=(
                    "strategy-biglotto-backtest-"
                    + _canonical_sha256(
                        {
                            "run_id": run_id,
                            "strategy_id": strategy_id,
                            "strategy_source_sha256": (
                                source_identity.strategy_source_sha256
                            ),
                            "strategy_version": strategy_version,
                        }
                    )
                ),
                response_shape=response_shape,
            )
            for (
                strategy_id,
                strategy_name,
                strategy_version,
                lifecycle_status,
                governance_status,
                source_identity,
                response_shape,
            ) in provisional_strategies
        )
        return _PreparedRun(
            manifest=manifest,
            snapshot=snapshot,
            source_commit_oid=source_commit_oid,
            strategies=strategies,
            targets=tuple(targets),
            run_id=run_id,
            scoring_version=scoring_version,
        )

    def _execute_prepared(
        self,
        repository: ResearchStore,
        prepared: _PreparedRun,
        *,
        stop_requested: Event | None,
    ) -> RunBigLottoResearchBacktestResult:
        expected_target_count = len(prepared.targets) * len(prepared.strategies)
        prior_progress = repository.find_progress(prepared.run_id)
        if (
            prior_progress is not None
            and prior_progress.expected_target_count != expected_target_count
        ):
            raise ResearchBacktestConflictError(
                "stored run expected_target_count conflicts with the manifest"
            )
        completed_keys = _completed_target_key_set(repository, prepared.run_id)
        expected_keys = {
            (
                strategy.snapshot_id,
                LotteryType.BIG_LOTTO.value,
                target.row.draw_number,
            )
            for target in prepared.targets
            for strategy in prepared.strategies
        }
        if not completed_keys <= expected_keys:
            raise ResearchBacktestConflictError(
                "stored run contains a completed key outside the manifest"
            )
        if (
            prior_progress is not None
            and prior_progress.completed_target_count != len(completed_keys)
        ):
            raise ResearchBacktestConflictError(
                "stored progress count conflicts with completed natural keys"
            )

        if (
            prior_progress is not None
            and prior_progress.status is ResearchRunStatus.COMPLETED
        ):
            if completed_keys != expected_keys:
                raise ResearchBacktestConflictError(
                    "completed run does not contain every expected natural key"
                )
            counts = _decode_progress_cursor(
                prior_progress,
                strategy_ids=prepared.manifest.strategy_ids,
            )
            return _result(
                prepared,
                progress=prior_progress,
                counts=counts,
                targets_created=0,
                tickets_created=0,
                results_created=0,
                idempotent_no_op=True,
                interrupted=False,
            )

        counts = self._resume_counts(
            prior_progress,
            strategy_ids=prepared.manifest.strategy_ids,
        )
        if counts.completed_target_count != len(completed_keys):
            raise ResearchBacktestConflictError(
                "stored progress cursor conflicts with completed natural keys"
            )

        attempt = uuid.uuid4().hex
        rule_contract_id = repository.register_rule_contract(
            BIG_LOTTO_RULE_CONTRACT,
            idempotency_key=f"{attempt}:rule-contract",
        )
        manifest_bytes = prepared.manifest.canonical_file_bytes()
        manifest_artifact_id = repository.register_artifact(
            artifact_kind=BIG_LOTTO_RESEARCH_BACKTEST_RUN_MANIFEST_V1,
            source_locator=f"manifest:{prepared.manifest.manifest_sha256}",
            media_type="application/json",
            byte_length=len(manifest_bytes),
            artifact_sha256=sha256_hex(manifest_bytes),
            idempotency_key=f"{attempt}:manifest-artifact",
        )
        if prior_progress is None:
            repository.create_run(
                run_kind=ResearchRunKind.HISTORICAL_BACKTEST,
                rule_contract_id=rule_contract_id,
                input_dataset_identity=_dataset_identity(prepared.manifest),
                input_dataset_sha256=prepared.snapshot.source_snapshot_sha256,
                expected_target_count=expected_target_count,
                producer_identity=RESEARCH_BACKTEST_PRODUCER_IDENTITY,
                execution_code_version=RESEARCH_BACKTEST_RUNNER_VERSION,
                source_commit_oid=prepared.source_commit_oid,
                idempotency_key=f"{attempt}:create-run",
                run_id=prepared.run_id,
                imported_from_artifact_id=manifest_artifact_id,
            )
        elif prior_progress.status is ResearchRunStatus.PAUSED:
            repository.append_run_status(
                prepared.run_id,
                status=ResearchRunStatus.RUNNING,
                progress_cursor=_encode_progress_cursor(counts),
                idempotency_key=f"{attempt}:resume-running",
            )
        elif prior_progress.status is not ResearchRunStatus.RUNNING:
            raise ResearchBacktestRunStateError(
                f"run status {prior_progress.status.value} is not resumable"
            )

        for strategy in prepared.strategies:
            repository.register_strategy_snapshot(
                prepared.run_id,
                StrategySnapshotInput(
                    lottery_type=LotteryType.BIG_LOTTO.value,
                    strategy_id=strategy.strategy_id,
                    strategy_name=strategy.strategy_name,
                    strategy_version=strategy.strategy_version,
                    provenance_availability=(
                        StrategyProvenanceAvailability.COMPLETE
                    ),
                    source_commit_oid=prepared.source_commit_oid,
                    strategy_source_sha256=(
                        strategy.source_identity.strategy_source_sha256
                    ),
                    producer_identity=RESEARCH_BACKTEST_PRODUCER_IDENTITY,
                    producer_version=RESEARCH_BACKTEST_RUNNER_VERSION,
                    runtime_fingerprint=(
                        strategy.source_identity.runtime_fingerprint
                    ),
                    parameters_json=_strategy_parameters_json(
                        prepared,
                        strategy,
                    ),
                    seed_protocol=RESEARCH_BACKTEST_SEED_PROTOCOL,
                    replicate=prepared.manifest.replicate,
                    execution_code_version=RESEARCH_BACKTEST_RUNNER_VERSION,
                    governance_status=strategy.governance_status,
                    lifecycle_status=strategy.lifecycle_status,
                ),
                idempotency_key=(
                    f"{attempt}:strategy:{strategy.strategy_id}:"
                    f"{strategy.strategy_version}"
                ),
                snapshot_id=strategy.snapshot_id,
            )

        targets_created = 0
        tickets_created = 0
        results_created = 0
        result_verification_exercised = False
        for target_ordinal, target in enumerate(prepared.targets):
            for strategy_ordinal, strategy in enumerate(prepared.strategies):
                natural_key = (
                    strategy.snapshot_id,
                    LotteryType.BIG_LOTTO.value,
                    target.row.draw_number,
                )
                if natural_key in completed_keys:
                    continue
                target_order = (
                    target_ordinal * len(prepared.strategies)
                    + strategy_ordinal
                )
                attempt_commit = self._build_attempt_commit(
                    prepared,
                    target,
                    strategy,
                    target_order=target_order,
                )
                committed = repository.commit_target(
                    attempt_commit.value,
                    idempotency_key=(
                        f"{attempt}:target:{strategy.snapshot_id}:"
                        f"{target.row.draw_number}"
                    ),
                )
                if committed.verified_no_op:
                    raise ResearchBacktestConflictError(
                        "resume index missed an already-complete target"
                    )
                if (
                    attempt_commit.result_count
                    and not result_verification_exercised
                ):
                    result_draw = attempt_commit.value.result_draw
                    if result_draw is None:  # pragma: no cover - typed invariant
                        raise ResearchBacktestConflictError(
                            "scored target is missing its result draw"
                        )
                    verified_insertions = repository.commit_ticket_results(
                        committed.target_id,
                        result_draw,
                        attempt_commit.value.ticket_results,
                        idempotency_key=f"{attempt}:verify-ticket-results",
                    )
                    if verified_insertions != 0:
                        raise ResearchBacktestConflictError(
                            "atomic ticket results were not already complete"
                        )
                    result_verification_exercised = True
                completed_keys.add(natural_key)
                counts.record(strategy.strategy_id, attempt_commit.status)
                targets_created += 1
                tickets_created += attempt_commit.ticket_count
                results_created += attempt_commit.result_count
                if stop_requested is not None and stop_requested.is_set():
                    cursor = _encode_progress_cursor(counts)
                    repository.append_run_status(
                        prepared.run_id,
                        status=ResearchRunStatus.PAUSED,
                        progress_cursor=cursor,
                        idempotency_key=f"{attempt}:safe-pause",
                    )
                    paused = repository.progress(prepared.run_id)
                    return _result(
                        prepared,
                        progress=paused,
                        counts=counts,
                        targets_created=targets_created,
                        tickets_created=tickets_created,
                        results_created=results_created,
                        idempotent_no_op=False,
                        interrupted=True,
                    )

        if completed_keys != expected_keys:
            raise ResearchBacktestConflictError(
                "runner ended without every expected natural key"
            )
        final_cursor = _encode_progress_cursor(counts)
        repository.append_run_status(
            prepared.run_id,
            status=ResearchRunStatus.RUNNING,
            progress_cursor=final_cursor,
            idempotency_key=f"{attempt}:final-running-checkpoint",
        )
        self._store_summaries(
            repository,
            prepared,
            counts,
            attempt=attempt,
        )
        before_completion = repository.progress(prepared.run_id)
        if before_completion.completed_target_count != expected_target_count:
            raise ResearchBacktestConflictError(
                "run completion count does not match the manifest"
            )
        repository.append_run_status(
            prepared.run_id,
            status=ResearchRunStatus.COMPLETED,
            progress_cursor=final_cursor,
            idempotency_key=f"{attempt}:completed",
        )
        final = repository.progress(prepared.run_id)
        return _result(
            prepared,
            progress=final,
            counts=counts,
            targets_created=targets_created,
            tickets_created=tickets_created,
            results_created=results_created,
            idempotent_no_op=False,
            interrupted=False,
        )

    @staticmethod
    def _resume_counts(
        prior_progress: RunProgress | None,
        *,
        strategy_ids: tuple[str, ...],
    ) -> _ProgressCounts:
        if prior_progress is None:
            return _ProgressCounts(strategy_ids)
        if (
            prior_progress.status is ResearchRunStatus.RUNNING
            and prior_progress.completed_target_count == 0
            and prior_progress.progress_cursor is None
        ):
            return _ProgressCounts(strategy_ids)
        return _decode_progress_cursor(
            prior_progress,
            strategy_ids=strategy_ids,
        )

    def _build_attempt_commit(
        self,
        prepared: _PreparedRun,
        target: _PreparedTarget,
        strategy: _PreparedStrategy,
        *,
        target_order: int,
    ) -> _AttemptCommit:
        manifest = prepared.manifest
        history = target.bounded_history
        history_cutoff = _draw_binding(history[-1], manifest)
        target_draw = _draw_binding(target.row, manifest)
        if len(history) < manifest.minimum_history_draws:
            status = ResearchExecutionStatus.INSUFFICIENT_HISTORY
            return _AttemptCommit(
                value=TargetCommitInput(
                    run_id=prepared.run_id,
                    strategy_snapshot_id=strategy.snapshot_id,
                    target_order=target_order,
                    input_dataset_identity=_dataset_identity(manifest),
                    input_dataset_sha256=(
                        prepared.snapshot.source_snapshot_sha256
                    ),
                    history_cutoff=history_cutoff,
                    history_draw_count=len(history),
                    source_history_order=(
                        RESEARCH_BACKTEST_SOURCE_HISTORY_ORDER
                    ),
                    target_draw=target_draw,
                    causal_eligible=False,
                    candidate_k=None,
                    combination_count=None,
                    ticket_count_prefix=None,
                    tickets=(),
                    execution_status=status,
                    closure=ClosureInput(
                        closure_type=status,
                        reason_code="AVAILABLE_HISTORY_BELOW_MINIMUM",
                    ),
                ),
                status=status,
                ticket_count=0,
                result_count=0,
            )

        causal_history = tuple(_causal_row(row) for row in history)
        if strategy.response_shape is ResponseShape.PORTFOLIO:
            return self._build_portfolio_attempt_commit(
                prepared,
                target,
                strategy,
                causal_history,
                history_cutoff=history_cutoff,
                target_draw=target_draw,
                target_order=target_order,
            )
        try:
            generated = self._generate.execute(
                GenerateOrderedCandidateEmissionInput(
                    strategy_id=strategy.strategy_id,
                    lottery_type=LotteryType.BIG_LOTTO,
                    history=causal_history,
                    replicate=manifest.replicate,
                    target_draw=target.row.draw_number,
                    history_cutoff=history[-1].draw_number,
                )
            )
        except Exception:
            return self._closed_attempt(
                prepared,
                target,
                strategy,
                target_order=target_order,
                status=ResearchExecutionStatus.EXECUTION_ERROR,
                reason_code="REPLAY_ERROR",
                sanitized_detail="strategy execution failed safely",
            )
        if generated.legal_bet.status is not GenerateOneBetStatus.OK:
            mapped_status = _EXECUTION_STATUS_MAP[generated.legal_bet.status]
            reason = generated.legal_bet.reason_code
            return self._closed_attempt(
                prepared,
                target,
                strategy,
                target_order=target_order,
                status=mapped_status,
                reason_code=(
                    generated.legal_bet.status.value
                    if reason is None
                    else reason.value
                ),
                sanitized_detail=None,
            )

        numbers = generated.legal_bet.numbers
        emission = generated.emission
        if numbers is None or emission is None:  # pragma: no cover - typed invariant
            return self._closed_attempt(
                prepared,
                target,
                strategy,
                target_order=target_order,
                status=ResearchExecutionStatus.INVALID_OUTPUT,
                reason_code="INVALID_OUTPUT",
                sanitized_detail=None,
            )
        score = score_big_lotto_ticket(
            predicted_main_numbers=numbers,
            winning_main_numbers=target.row.main_numbers,
            winning_special_number=target.row.special_numbers[0],
        )
        prize = resolve_big_lotto_prize_tier(
            score.main_hits,
            score.special_hit,
        )
        prize_tier_id = (
            prize.tier_id.value
            if isinstance(prize, BigLottoPrizeTier)
            else prize.value
        )
        hit_numbers = tuple(
            sorted(set(numbers).intersection(target.row.main_numbers))
        )
        ticket = TicketInput(
            native_position=1,
            ordered_portfolio_position=1,
            canonical_ticket_json=_canonical_json(
                {
                    "main_numbers": list(numbers),
                    "special_numbers": [],
                }
            ),
        )
        ticket_result = TicketResultInput(
            ticket_native_position=1,
            ticket_count_prefix=1,
            main_hit_count=score.main_hits,
            special_hit_count=int(score.special_hit),
            prize_tier_id=prize_tier_id,
            hit_numbers_json=_canonical_json(list(hit_numbers)),
        )
        return _AttemptCommit(
            value=TargetCommitInput(
                run_id=prepared.run_id,
                strategy_snapshot_id=strategy.snapshot_id,
                target_order=target_order,
                input_dataset_identity=_dataset_identity(manifest),
                input_dataset_sha256=prepared.snapshot.source_snapshot_sha256,
                history_cutoff=history_cutoff,
                history_draw_count=len(history),
                source_history_order=RESEARCH_BACKTEST_SOURCE_HISTORY_ORDER,
                target_draw=target_draw,
                causal_eligible=True,
                candidate_k=len(emission.emitted_main_numbers),
                combination_count=1,
                ticket_count_prefix=1,
                tickets=(ticket,),
                execution_status=ResearchExecutionStatus.OK,
                result_draw=target_draw,
                ticket_results=(ticket_result,),
            ),
            status=ResearchExecutionStatus.OK,
            ticket_count=1,
            result_count=1,
        )

    def _build_portfolio_attempt_commit(
        self,
        prepared: _PreparedRun,
        target: _PreparedTarget,
        strategy: _PreparedStrategy,
        causal_history: tuple[CausalDrawRow, ...],
        *,
        history_cutoff: DrawBindingInput,
        target_draw: DrawBindingInput,
        target_order: int,
    ) -> _AttemptCommit:
        manifest = prepared.manifest
        history = target.bounded_history
        try:
            generated = self._generate_portfolio.execute(
                GenerateOrderedPortfolioEmissionInput(
                    strategy_id=strategy.strategy_id,
                    lottery_type=LotteryType.BIG_LOTTO,
                    history=causal_history,
                    replicate=manifest.replicate,
                    target_draw=target.row.draw_number,
                    history_cutoff=history[-1].draw_number,
                )
            )
        except Exception:
            return self._closed_attempt(
                prepared,
                target,
                strategy,
                target_order=target_order,
                status=ResearchExecutionStatus.EXECUTION_ERROR,
                reason_code="REPLAY_ERROR",
                sanitized_detail="strategy execution failed safely",
            )
        if generated.legal_bets.status is not GeneratePortfolioStatus.OK:
            mapped_status = _EXECUTION_STATUS_MAP_PORTFOLIO[generated.legal_bets.status]
            reason = generated.legal_bets.reason_code
            return self._closed_attempt(
                prepared,
                target,
                strategy,
                target_order=target_order,
                status=mapped_status,
                reason_code=(
                    generated.legal_bets.status.value
                    if reason is None
                    else reason.value
                ),
                sanitized_detail=None,
            )

        numbers = generated.legal_bets.numbers
        emissions = generated.emissions
        if (
            numbers is None  # pragma: no cover - typed invariant
            or emissions is None
            or len(numbers) != len(emissions)
        ):
            return self._closed_attempt(
                prepared,
                target,
                strategy,
                target_order=target_order,
                status=ResearchExecutionStatus.INVALID_OUTPUT,
                reason_code="INVALID_OUTPUT",
                sanitized_detail=None,
            )

        candidate_lengths = {
            len(emission.emitted_main_numbers) for emission in emissions
        }
        if len(candidate_lengths) != 1:
            return self._closed_attempt(
                prepared,
                target,
                strategy,
                target_order=target_order,
                status=ResearchExecutionStatus.INVALID_OUTPUT,
                reason_code="INVALID_OUTPUT",
                sanitized_detail=None,
            )
        candidate_k = candidate_lengths.pop()

        native_ticket_count = len(numbers)
        tickets: list[TicketInput] = []
        ticket_results: list[TicketResultInput] = []
        for index, ticket_numbers in enumerate(numbers):
            position = index + 1
            score = score_big_lotto_ticket(
                predicted_main_numbers=ticket_numbers,
                winning_main_numbers=target.row.main_numbers,
                winning_special_number=target.row.special_numbers[0],
            )
            prize = resolve_big_lotto_prize_tier(
                score.main_hits,
                score.special_hit,
            )
            prize_tier_id = (
                prize.tier_id.value
                if isinstance(prize, BigLottoPrizeTier)
                else prize.value
            )
            hit_numbers = tuple(
                sorted(set(ticket_numbers).intersection(target.row.main_numbers))
            )
            tickets.append(
                TicketInput(
                    native_position=position,
                    ordered_portfolio_position=position,
                    canonical_ticket_json=_canonical_json(
                        {
                            "main_numbers": list(ticket_numbers),
                            "special_numbers": [],
                        }
                    ),
                )
            )
            ticket_results.append(
                TicketResultInput(
                    ticket_native_position=position,
                    ticket_count_prefix=native_ticket_count,
                    main_hit_count=score.main_hits,
                    special_hit_count=int(score.special_hit),
                    prize_tier_id=prize_tier_id,
                    hit_numbers_json=_canonical_json(list(hit_numbers)),
                )
            )

        return _AttemptCommit(
            value=TargetCommitInput(
                run_id=prepared.run_id,
                strategy_snapshot_id=strategy.snapshot_id,
                target_order=target_order,
                input_dataset_identity=_dataset_identity(manifest),
                input_dataset_sha256=prepared.snapshot.source_snapshot_sha256,
                history_cutoff=history_cutoff,
                history_draw_count=len(history),
                source_history_order=RESEARCH_BACKTEST_SOURCE_HISTORY_ORDER,
                target_draw=target_draw,
                causal_eligible=True,
                candidate_k=candidate_k,
                combination_count=native_ticket_count,
                ticket_count_prefix=native_ticket_count,
                tickets=tuple(tickets),
                execution_status=ResearchExecutionStatus.OK,
                result_draw=target_draw,
                ticket_results=tuple(ticket_results),
            ),
            status=ResearchExecutionStatus.OK,
            ticket_count=native_ticket_count,
            result_count=native_ticket_count,
        )

    @staticmethod
    def _closed_attempt(
        prepared: _PreparedRun,
        target: _PreparedTarget,
        strategy: _PreparedStrategy,
        *,
        target_order: int,
        status: ResearchExecutionStatus,
        reason_code: str,
        sanitized_detail: str | None,
    ) -> _AttemptCommit:
        history = target.bounded_history
        manifest = prepared.manifest
        return _AttemptCommit(
            value=TargetCommitInput(
                run_id=prepared.run_id,
                strategy_snapshot_id=strategy.snapshot_id,
                target_order=target_order,
                input_dataset_identity=_dataset_identity(manifest),
                input_dataset_sha256=prepared.snapshot.source_snapshot_sha256,
                history_cutoff=_draw_binding(history[-1], manifest),
                history_draw_count=len(history),
                source_history_order=RESEARCH_BACKTEST_SOURCE_HISTORY_ORDER,
                target_draw=_draw_binding(target.row, manifest),
                causal_eligible=True,
                candidate_k=None,
                combination_count=None,
                ticket_count_prefix=None,
                tickets=(),
                execution_status=status,
                closure=ClosureInput(
                    closure_type=status,
                    reason_code=reason_code,
                    sanitized_detail=sanitized_detail,
                ),
            ),
            status=status,
            ticket_count=0,
            result_count=0,
        )

    @staticmethod
    def _store_summaries(
        repository: ResearchStore,
        prepared: _PreparedRun,
        counts: _ProgressCounts,
        *,
        attempt: str,
    ) -> None:
        manifest = prepared.manifest
        status_counts = _status_count_document(counts.status_counts)
        repository.store_run_summary(
            RunSummaryInput(
                run_id=prepared.run_id,
                strategy_snapshot_id=None,
                summary_kind="AUDIT",
                ticket_count_prefix=None,
                summary_version=RESEARCH_BACKTEST_SUMMARY_VERSION,
                denominator_count=counts.completed_target_count,
                successful_count=counts.status_counts[
                    ResearchExecutionStatus.OK
                ],
                closed_count=(
                    counts.completed_target_count
                    - counts.status_counts[ResearchExecutionStatus.OK]
                ),
                rank_value=None,
                canonical_summary_json=_canonical_json(
                    {
                        "completed_target_count": (
                            counts.completed_target_count
                        ),
                        "expected_target_count": (
                            len(prepared.targets)
                            * len(prepared.strategies)
                        ),
                        "manifest_sha256": manifest.manifest_sha256,
                        "ordered_strategy_ids": list(manifest.strategy_ids),
                        "ordered_target_draws": list(manifest.target_draws),
                        "run_id": prepared.run_id,
                        "runner_source_commit_oid": (
                            prepared.source_commit_oid
                        ),
                        "scoring_semantics": (
                            RESEARCH_BACKTEST_SCORING_SEMANTICS
                        ),
                        "scoring_version": prepared.scoring_version,
                        "source_snapshot_sha256": (
                            prepared.snapshot.source_snapshot_sha256
                        ),
                        "status_counts": status_counts,
                    }
                ),
            ),
            idempotency_key=f"{attempt}:summary:run",
            summary_id=f"{prepared.run_id}:summary:audit:v1",
        )
        for strategy in prepared.strategies:
            strategy_counts = counts.strategy_status_counts[
                strategy.strategy_id
            ]
            ok_count = strategy_counts[ResearchExecutionStatus.OK]
            denominator = sum(strategy_counts.values())
            repository.store_run_summary(
                RunSummaryInput(
                    run_id=prepared.run_id,
                    strategy_snapshot_id=strategy.snapshot_id,
                    summary_kind="COVERAGE",
                    ticket_count_prefix=None,
                    summary_version=RESEARCH_BACKTEST_SUMMARY_VERSION,
                    denominator_count=denominator,
                    successful_count=ok_count,
                    closed_count=denominator - ok_count,
                    rank_value=None,
                    canonical_summary_json=_canonical_json(
                        {
                            "closed_count": denominator - ok_count,
                            "denominator_count": denominator,
                            "ok_count": ok_count,
                            "result_count": ok_count,
                            "scoring_semantics": (
                                RESEARCH_BACKTEST_SCORING_SEMANTICS
                            ),
                            "scoring_version": prepared.scoring_version,
                            "status_counts": _status_count_document(
                                strategy_counts
                            ),
                            "strategy_id": strategy.strategy_id,
                            "strategy_snapshot_id": strategy.snapshot_id,
                            "strategy_version": strategy.strategy_version,
                            "ticket_count": ok_count,
                        }
                    ),
                ),
                idempotency_key=(
                    f"{attempt}:summary:strategy:{strategy.snapshot_id}"
                ),
                summary_id=(
                    f"{prepared.run_id}:summary:coverage:"
                    f"{strategy.snapshot_id}:v1"
                ),
            )


_EXECUTION_STATUS_MAP: Mapping[
    GenerateOneBetStatus,
    ResearchExecutionStatus,
] = {
    GenerateOneBetStatus.REJECTED: ResearchExecutionStatus.REJECTED,
    GenerateOneBetStatus.INSUFFICIENT_HISTORY: (
        ResearchExecutionStatus.INSUFFICIENT_HISTORY
    ),
    GenerateOneBetStatus.STRATEGY_UNAVAILABLE: (
        ResearchExecutionStatus.STRATEGY_UNAVAILABLE
    ),
    GenerateOneBetStatus.WRONG_RESPONSE_PATH: (
        ResearchExecutionStatus.STRATEGY_UNAVAILABLE
    ),
    GenerateOneBetStatus.INVALID_OUTPUT: ResearchExecutionStatus.INVALID_OUTPUT,
    GenerateOneBetStatus.REPLAY_ERROR: ResearchExecutionStatus.EXECUTION_ERROR,
}


_EXECUTION_STATUS_MAP_PORTFOLIO: Mapping[
    GeneratePortfolioStatus,
    ResearchExecutionStatus,
] = {
    GeneratePortfolioStatus.INSUFFICIENT_HISTORY: (
        ResearchExecutionStatus.INSUFFICIENT_HISTORY
    ),
    GeneratePortfolioStatus.STRATEGY_UNAVAILABLE: (
        ResearchExecutionStatus.STRATEGY_UNAVAILABLE
    ),
    GeneratePortfolioStatus.WRONG_RESPONSE_PATH: (
        ResearchExecutionStatus.STRATEGY_UNAVAILABLE
    ),
    GeneratePortfolioStatus.INVALID_OUTPUT: ResearchExecutionStatus.INVALID_OUTPUT,
    GeneratePortfolioStatus.REPLAY_ERROR: ResearchExecutionStatus.EXECUTION_ERROR,
}


def _required_string(document: Mapping[str, object], key: str) -> str:
    value = document.get(key)
    if type(value) is not str:
        raise ResearchBacktestInputError(
            "INVALID_MANIFEST_FIELD_TYPE",
            f"manifest {key} must be a string",
        )
    return value


def _required_int(document: Mapping[str, object], key: str) -> int:
    value = document.get(key)
    if type(value) is not int:
        raise ResearchBacktestInputError(
            "INVALID_MANIFEST_FIELD_TYPE",
            f"manifest {key} must be an integer",
        )
    return value


def _required_string_tuple(
    document: Mapping[str, object],
    key: str,
) -> tuple[str, ...]:
    value = document.get(key)
    if not isinstance(value, list):
        raise ResearchBacktestInputError(
            "INVALID_MANIFEST_FIELD_TYPE",
            f"manifest {key} must be an array",
        )
    values = cast(list[object], value)
    if any(type(item) is not str for item in values):
        raise ResearchBacktestInputError(
            "INVALID_MANIFEST_FIELD_TYPE",
            f"manifest {key} must contain only strings",
        )
    return tuple(cast(str, item) for item in values)


def _enum_value[EnumType: StrEnum](
    enum_type: type[EnumType],
    document: Mapping[str, object],
    key: str,
    reason_code: str,
) -> EnumType:
    value = _required_string(document, key)
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ResearchBacktestInputError(
            reason_code,
            f"manifest {key} is unsupported",
        ) from exc


def _dataset_identity(
    manifest: BigLottoResearchBacktestManifest,
) -> str:
    return f"{manifest.dataset_id}:{manifest.dataset_version}"


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_canonical_json(raw: str, label: str) -> None:
    try:
        decoded = cast(object, json.loads(raw))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be canonical JSON") from exc
    if _canonical_json(decoded) != raw:
        raise ValueError(f"{label} must be canonical JSON")


def _governance_status(provenance: tuple[str, ...]) -> str:
    for item in provenance:
        if item.startswith("evidence_status:"):
            return item.partition(":")[2]
    return "CATALOG_DECLARED"


def _scoring_version() -> str:
    prize = BIG_LOTTO_RULE_CONTRACT.prize_rule
    assert prize is not None
    return (
        f"{BIG_LOTTO_RULE_CONTRACT.contract_version}:"
        f"{prize.schema_version}:{prize.source_sha256}"
    )


def _strategy_parameters_json(
    prepared: _PreparedRun,
    strategy: _PreparedStrategy,
) -> str:
    manifest = prepared.manifest
    return _canonical_json(
        {
            "dataset_id": manifest.dataset_id,
            "dataset_version": manifest.dataset_version,
            "manifest_sha256": manifest.manifest_sha256,
            "maximum_history_draws": manifest.maximum_history_draws,
            "minimum_history_draws": manifest.minimum_history_draws,
            "replicate": manifest.replicate,
            "scoring_semantics": RESEARCH_BACKTEST_SCORING_SEMANTICS,
            "scoring_version": prepared.scoring_version,
            "source_history_order": RESEARCH_BACKTEST_SOURCE_HISTORY_ORDER,
            "source_snapshot_sha256": (
                prepared.snapshot.source_snapshot_sha256
            ),
            "strategy_id": strategy.strategy_id,
            "strategy_version": strategy.strategy_version,
        }
    )


def _draw_binding(
    row: OrderedCandidateSourceRow,
    manifest: BigLottoResearchBacktestManifest,
) -> DrawBindingInput:
    return DrawBindingInput(
        lottery_type=LotteryType.BIG_LOTTO.value,
        draw_number=row.draw_number,
        draw_date=row.draw_date.isoformat(),
        main_numbers_json=_canonical_json(list(row.main_numbers)),
        special_numbers_json=_canonical_json(list(row.special_numbers)),
        draw_sha256=row.normalized_record_hash,
        draw_data_version=manifest.dataset_version,
    )


def _causal_row(row: OrderedCandidateSourceRow) -> CausalDrawRow:
    return CausalDrawRow(
        draw=row.draw_number,
        date=row.draw_date.isoformat(),
        numbers=row.main_numbers,
    )


def _completed_target_key_set(
    repository: ResearchStore,
    run_id: str,
) -> set[tuple[str, str, str]]:
    completed: set[tuple[str, str, str]] = set()
    after: CompletedTargetCursor | None = None
    while True:
        page = repository.completed_target_keys(
            run_id,
            limit=500,
            after=after,
        )
        for item in page.items:
            if item in completed:
                raise ResearchBacktestConflictError(
                    "completed target pagination returned a duplicate key"
                )
            completed.add(item)
        if page.next_cursor is None:
            return completed
        if not isinstance(page.next_cursor, CompletedTargetCursor):
            raise ResearchBacktestConflictError(
                "completed target pagination returned an invalid cursor type"
            )
        after = page.next_cursor


def _status_count_document(
    counts: Mapping[ResearchExecutionStatus, int],
) -> dict[str, int]:
    return {
        status.value: counts.get(status, 0)
        for status in ResearchExecutionStatus
    }


def _encode_progress_cursor(counts: _ProgressCounts) -> str:
    return _canonical_json(
        {
            "completed_target_count": counts.completed_target_count,
            "schema_version": RESEARCH_BACKTEST_PROGRESS_SCHEMA_VERSION,
            "status_counts": _status_count_document(counts.status_counts),
            "strategy_status_counts": {
                strategy_id: _status_count_document(strategy_counts)
                for strategy_id, strategy_counts in sorted(
                    counts.strategy_status_counts.items()
                )
            },
        }
    )


def _decode_progress_cursor(
    progress: RunProgress,
    *,
    strategy_ids: tuple[str, ...],
) -> _ProgressCounts:
    if progress.progress_cursor is None:
        raise ResearchBacktestConflictError(
            "stored progress is missing its deterministic cursor"
        )
    try:
        raw = cast(object, json.loads(progress.progress_cursor))
    except (TypeError, ValueError) as exc:
        raise ResearchBacktestConflictError(
            "stored progress cursor is not valid JSON"
        ) from exc
    if not isinstance(raw, dict):
        raise ResearchBacktestConflictError(
            "stored progress cursor is not an object"
        )
    document = cast(dict[str, object], raw)
    if set(document) != {
        "completed_target_count",
        "schema_version",
        "status_counts",
        "strategy_status_counts",
    }:
        raise ResearchBacktestConflictError(
            "stored progress cursor fields are invalid"
        )
    if document["schema_version"] != RESEARCH_BACKTEST_PROGRESS_SCHEMA_VERSION:
        raise ResearchBacktestConflictError(
            "stored progress cursor version is unsupported"
        )
    status_counts = _decode_status_counts(document["status_counts"])
    strategy_raw = document["strategy_status_counts"]
    if not isinstance(strategy_raw, dict):
        raise ResearchBacktestConflictError(
            "stored strategy progress is invalid"
        )
    strategy_document = cast(dict[str, object], strategy_raw)
    if set(strategy_document) != set(strategy_ids):
        raise ResearchBacktestConflictError(
            "stored strategy progress conflicts with the manifest"
        )
    strategy_counts = {
        strategy_id: _decode_status_counts(strategy_document[strategy_id])
        for strategy_id in strategy_ids
    }
    counts = _ProgressCounts(
        strategy_ids,
        status_counts=status_counts,
        strategy_status_counts=strategy_counts,
    )
    completed = document["completed_target_count"]
    if (
        type(completed) is not int
        or completed != counts.completed_target_count
        or completed != progress.completed_target_count
    ):
        raise ResearchBacktestConflictError(
            "stored progress cursor count is inconsistent"
        )
    if any(
        sum(strategy_counts[strategy_id].values())
        > counts.completed_target_count
        for strategy_id in strategy_ids
    ):
        raise ResearchBacktestConflictError(
            "stored per-strategy progress is inconsistent"
        )
    if (
        sum(
            sum(strategy_counts[strategy_id].values())
            for strategy_id in strategy_ids
        )
        != counts.completed_target_count
    ):
        raise ResearchBacktestConflictError(
            "stored per-strategy progress does not reconcile"
        )
    for status in ResearchExecutionStatus:
        if counts.status_counts[status] != sum(
            strategy_counts[strategy_id][status]
            for strategy_id in strategy_ids
        ):
            raise ResearchBacktestConflictError(
                "stored run and strategy status counts do not reconcile"
            )
    return counts


def _decode_status_counts(
    raw: object,
) -> dict[ResearchExecutionStatus, int]:
    if not isinstance(raw, dict):
        raise ResearchBacktestConflictError(
            "stored status counts are invalid"
        )
    document = cast(dict[str, object], raw)
    expected = {status.value for status in ResearchExecutionStatus}
    if set(document) != expected:
        raise ResearchBacktestConflictError(
            "stored status vocabulary is invalid"
        )
    counts: dict[ResearchExecutionStatus, int] = {}
    for status in ResearchExecutionStatus:
        value = document[status.value]
        if type(value) is not int or value < 0:
            raise ResearchBacktestConflictError(
                "stored status count is invalid"
            )
        counts[status] = value
    return counts


def _result(
    prepared: _PreparedRun,
    *,
    progress: RunProgress,
    counts: _ProgressCounts,
    targets_created: int,
    tickets_created: int,
    results_created: int,
    idempotent_no_op: bool,
    interrupted: bool,
) -> RunBigLottoResearchBacktestResult:
    return RunBigLottoResearchBacktestResult(
        run_id=prepared.run_id,
        status=progress.status,
        manifest_sha256=prepared.manifest.manifest_sha256,
        source_snapshot_sha256=prepared.snapshot.source_snapshot_sha256,
        expected_target_count=progress.expected_target_count,
        completed_target_count=progress.completed_target_count,
        targets_created=targets_created,
        tickets_created=tickets_created,
        results_created=results_created,
        status_counts=tuple(
            (status, counts.status_counts[status])
            for status in ResearchExecutionStatus
        ),
        idempotent_no_op=idempotent_no_op,
        interrupted=interrupted,
    )


__all__ = [
    "BIG_LOTTO_RESEARCH_BACKTEST_RUN_MANIFEST_V1",
    "RESEARCH_BACKTEST_PROGRESS_SCHEMA_VERSION",
    "RESEARCH_BACKTEST_RUNNER_VERSION",
    "BigLottoResearchBacktestManifest",
    "BigLottoSourceSnapshotReader",
    "ResearchBacktestConflictError",
    "ResearchBacktestError",
    "ResearchBacktestInputError",
    "ResearchBacktestProvenanceError",
    "ResearchBacktestRunStateError",
    "ResearchBacktestSourceError",
    "RunBigLottoResearchBacktest",
    "RunBigLottoResearchBacktestResult",
    "StrategySourceIdentity",
    "StrategySourceIdentityResolver",
]
