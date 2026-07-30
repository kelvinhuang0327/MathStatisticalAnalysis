"""Import sealed BIG_LOTTO legacy replays as a reference baseline."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import threading
import time
import uuid
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

from lottolab.application.research_store import (
    CompletedTargetCursor,
    DrawBindingInput,
    ResearchStore,
    RunSummaryInput,
    StrategySnapshotInput,
    TargetCommitInput,
    TicketInput,
    TicketResultInput,
)
from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    score_big_lotto_ticket,
)
from lottolab.domain.research import (
    ResearchExecutionStatus,
    ResearchRunKind,
    ResearchRunStatus,
    StrategyProvenanceAvailability,
)

CORPUS_ROOT_NAME = "LOTTOLAB_LEGACY_REFERENCE_CORPUS_V1"
REPLAY_TABLE_RELATIVE_PATH = "tables/strategy_prediction_replays.jsonl"
DRAWS_TABLE_RELATIVE_PATH = "tables/draws.jsonl"
IMPORTER_IDENTITY = (
    "lottolab.application.legacy_reference_import."
    "BigLottoLegacyReferenceImporter"
)
IMPORTER_VERSION = "1.0.0"
SCORING_SAMPLE_SIZE = 500
_BIG_LOTTO = "BIG_LOTTO"
_FORBIDDEN_PATH_PARTS = frozenset({".local", "snapshots"})


class LegacyReferenceImportError(RuntimeError):
    """The sealed legacy corpus could not be imported honestly."""


class CorpusChecksumMismatchError(LegacyReferenceImportError):
    """A corpus file does not match its sealed SHA-256."""


class UnsupportedLegacyLotteryTypeError(LegacyReferenceImportError):
    """A row belongs to a lottery without a registered rule contract."""

    def __init__(self, lottery_type: str) -> None:
        self.lottery_type = lottery_type
        super().__init__(
            f"{lottery_type} is deferred: no reviewed lottery rule contract exists"
        )


class LegacyCausalCutoffError(LegacyReferenceImportError):
    """A legacy target is not strictly after its declared history cutoff."""


@dataclass(frozen=True, slots=True)
class CorpusFileEvidence:
    relative_path: str
    absolute_path: Path
    byte_length: int
    sha256: str


@dataclass(frozen=True, slots=True)
class LegacyDraw:
    draw_number: str
    draw_date: str
    main_numbers: tuple[int, ...]
    special_number: int
    draw_sha256: str
    draw_data_version: str
    history_ordinal: int

    def binding(self) -> DrawBindingInput:
        return DrawBindingInput(
            lottery_type=_BIG_LOTTO,
            draw_number=self.draw_number,
            draw_date=self.draw_date,
            main_numbers_json=_canonical_json(list(self.main_numbers)),
            special_numbers_json=_canonical_json([self.special_number]),
            draw_sha256=self.draw_sha256,
            draw_data_version=self.draw_data_version,
        )


@dataclass(frozen=True, slots=True)
class LegacyReplayRow:
    raw_record_json: str
    strategy_id: str
    strategy_name: str
    strategy_version: str
    target_draw: str
    target_date: str
    history_cutoff_draw: str
    bet_index: int
    predicted_numbers: tuple[int, ...]
    predicted_special: int | None
    actual_numbers: tuple[int, ...]
    actual_special: int
    hit_numbers: tuple[int, ...]
    hit_count: int
    special_hit: int
    provenance_hash: str | None
    provenance_source: str | None


@dataclass(frozen=True, slots=True)
class LegacyStrategy:
    strategy_id: str
    strategy_name: str
    strategy_version: str
    snapshot_id: str


@dataclass(frozen=True, slots=True)
class LegacyTarget:
    strategy: LegacyStrategy
    target_order: int
    history_cutoff: LegacyDraw
    target_draw: LegacyDraw
    rows: tuple[LegacyReplayRow, ...]


@dataclass(frozen=True, slots=True)
class LegacyScoringComparison:
    sample_size: int
    agreements: int
    disagreements: int
    main_hit_agreements: int
    special_hit_agreements: int
    disagreement_examples: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class PreparedLegacyCorpus:
    replay_file: CorpusFileEvidence
    draws_file: CorpusFileEvidence
    targets: tuple[LegacyTarget, ...]
    strategies: tuple[LegacyStrategy, ...]
    big_lotto_rows: int
    deferred_rows: tuple[tuple[str, int], ...]
    duplicate_ticket_rows: int
    scoring: LegacyScoringComparison


@dataclass(frozen=True, slots=True)
class LegacyImportResult:
    run_id: str
    status: ResearchRunStatus
    big_lotto_rows: int
    targets_created: int
    tickets_created: int
    results_created: int
    completed_target_count: int
    expected_target_count: int
    deferred_rows: tuple[tuple[str, int], ...]
    duplicate_ticket_rows: int
    scoring: LegacyScoringComparison
    idempotent_no_op: bool
    interrupted: bool
    target_duration_ms: tuple[float, ...]
    worst_reader_wait_ms: float
    elapsed_seconds: float

    @property
    def mean_target_ms(self) -> float:
        if not self.target_duration_ms:
            return 0.0
        return sum(self.target_duration_ms) / len(self.target_duration_ms)

    @property
    def p95_target_ms(self) -> float:
        if not self.target_duration_ms:
            return 0.0
        ordered = sorted(self.target_duration_ms)
        index = max(0, (95 * len(ordered) + 99) // 100 - 1)
        return ordered[index]

    def as_dict(self, *, include_duration_samples: bool = False) -> dict[str, object]:
        payload: dict[str, object] = {
            "big_lotto_rows": self.big_lotto_rows,
            "completed_target_count": self.completed_target_count,
            "deferred_rows": dict(self.deferred_rows),
            "duplicate_ticket_rows": self.duplicate_ticket_rows,
            "elapsed_seconds": self.elapsed_seconds,
            "expected_target_count": self.expected_target_count,
            "idempotent_no_op": self.idempotent_no_op,
            "interrupted": self.interrupted,
            "mean_target_ms": self.mean_target_ms,
            "p95_target_ms": self.p95_target_ms,
            "results_created": self.results_created,
            "run_id": self.run_id,
            "scoring_agreements": self.scoring.agreements,
            "scoring_disagreement_examples": list(
                self.scoring.disagreement_examples
            ),
            "scoring_disagreements": self.scoring.disagreements,
            "scoring_main_hit_agreements": self.scoring.main_hit_agreements,
            "scoring_sample_size": self.scoring.sample_size,
            "scoring_special_hit_agreements": self.scoring.special_hit_agreements,
            "status": self.status.value,
            "targets_created": self.targets_created,
            "tickets_created": self.tickets_created,
            "worst_reader_wait_ms": self.worst_reader_wait_ms,
        }
        if include_duration_samples:
            payload["target_duration_ms"] = list(self.target_duration_ms)
        return payload


class BigLottoLegacyReferenceImporter:
    """Own corpus validation, mapping, resume, and completion semantics."""

    def __init__(self, repository: ResearchStore) -> None:
        self._repository = repository

    def execute(
        self,
        corpus_root: Path,
        *,
        source_commit_oid: str,
        stop_requested: threading.Event | None = None,
        observe_reader_wait: bool = True,
    ) -> LegacyImportResult:
        started = time.perf_counter()
        _require_commit_oid(source_commit_oid)
        prepared = prepare_legacy_corpus(corpus_root)
        run_id = _stable_id(
            "run-reference-baseline-big-lotto",
            prepared.replay_file.sha256,
        )
        prior_progress = self._repository.find_progress(run_id)
        if prior_progress is not None and (
            prior_progress.expected_target_count != len(prepared.targets)
        ):
            raise LegacyReferenceImportError(
                "stored run target count conflicts with the sealed corpus"
            )
        if (
            prior_progress is not None
            and prior_progress.status is ResearchRunStatus.COMPLETED
        ):
            if prior_progress.completed_target_count != len(prepared.targets):
                raise LegacyReferenceImportError(
                    "completed run does not contain every expected target"
                )
            return LegacyImportResult(
                run_id=run_id,
                status=ResearchRunStatus.COMPLETED,
                big_lotto_rows=prepared.big_lotto_rows,
                targets_created=0,
                tickets_created=0,
                results_created=0,
                completed_target_count=prior_progress.completed_target_count,
                expected_target_count=prior_progress.expected_target_count,
                deferred_rows=prepared.deferred_rows,
                duplicate_ticket_rows=prepared.duplicate_ticket_rows,
                scoring=prepared.scoring,
                idempotent_no_op=True,
                interrupted=False,
                target_duration_ms=(),
                worst_reader_wait_ms=0.0,
                elapsed_seconds=time.perf_counter() - started,
            )

        attempt = uuid.uuid4().hex
        rule_contract_id = self._repository.register_rule_contract(
            BIG_LOTTO_RULE_CONTRACT,
            idempotency_key=f"{attempt}:rule-contract",
        )
        replay_artifact_id = self._register_corpus_artifact(
            prepared.replay_file,
            attempt=attempt,
        )
        self._register_corpus_artifact(prepared.draws_file, attempt=attempt)
        if prior_progress is None:
            self._repository.create_run(
                run_kind=ResearchRunKind.REFERENCE_BASELINE,
                rule_contract_id=rule_contract_id,
                input_dataset_identity=(
                    f"{CORPUS_ROOT_NAME}/{REPLAY_TABLE_RELATIVE_PATH}"
                ),
                input_dataset_sha256=prepared.replay_file.sha256,
                expected_target_count=len(prepared.targets),
                producer_identity=IMPORTER_IDENTITY,
                execution_code_version=IMPORTER_VERSION,
                source_commit_oid=source_commit_oid,
                idempotency_key=f"{attempt}:create-run",
                run_id=run_id,
                imported_from_artifact_id=replay_artifact_id,
            )
        elif prior_progress.status is ResearchRunStatus.PAUSED:
            self._repository.append_run_status(
                run_id,
                status=ResearchRunStatus.RUNNING,
                progress_cursor=str(prior_progress.completed_target_count),
                idempotency_key=f"{attempt}:resume-running",
            )

        for strategy in prepared.strategies:
            self._repository.register_strategy_snapshot(
                run_id,
                StrategySnapshotInput(
                    lottery_type=_BIG_LOTTO,
                    strategy_id=strategy.strategy_id,
                    strategy_name=strategy.strategy_name,
                    strategy_version=strategy.strategy_version,
                    provenance_availability=(
                        StrategyProvenanceAvailability.LEGACY_UNAVAILABLE
                    ),
                    source_commit_oid=None,
                    strategy_source_sha256=None,
                    producer_identity=IMPORTER_IDENTITY,
                    producer_version=IMPORTER_VERSION,
                    runtime_fingerprint=None,
                    parameters_json=None,
                    seed_protocol=None,
                    replicate=1,
                    execution_code_version=IMPORTER_VERSION,
                    governance_status="REFERENCE_BASELINE",
                    lifecycle_status="LEGACY_IMPORTED",
                ),
                idempotency_key=(
                    f"{attempt}:strategy:"
                    f"{strategy.strategy_id}:{strategy.strategy_version}"
                ),
                snapshot_id=strategy.snapshot_id,
            )

        completed = self._completed_target_key_set(run_id)
        durations: list[float] = []
        reader_waits: list[float] = []
        reader_errors: list[BaseException] = []
        reader_stop = threading.Event()
        reader_thread: threading.Thread | None = None
        if observe_reader_wait:
            reader_thread = threading.Thread(
                target=self._observe_reader_wait,
                args=(run_id, reader_stop, reader_waits, reader_errors),
                daemon=True,
                name="legacy-reference-import-reader",
            )
            reader_thread.start()

        targets_created = 0
        tickets_created = 0
        results_created = 0
        result_verification_exercised = False
        try:
            for target in prepared.targets:
                natural_key = (
                    target.strategy.snapshot_id,
                    _BIG_LOTTO,
                    target.target_draw.draw_number,
                )
                if natural_key in completed:
                    continue
                commit_input = self.build_target_commit_input(
                    run_id,
                    prepared,
                    target,
                )
                write_started = time.perf_counter()
                committed = self._repository.commit_target(
                    commit_input,
                    idempotency_key=(
                        f"{attempt}:target:{target.strategy.snapshot_id}:"
                        f"{target.target_draw.draw_number}"
                    ),
                )
                durations.append((time.perf_counter() - write_started) * 1_000)
                if committed.verified_no_op:
                    raise LegacyReferenceImportError(
                        "resume index missed an already-complete target"
                    )
                targets_created += 1
                tickets_created += len(target.rows)
                results_created += len(target.rows)
                if not result_verification_exercised:
                    verified_insertions = self._repository.commit_ticket_results(
                        committed.target_id,
                        commit_input.result_draw
                        if commit_input.result_draw is not None
                        else target.target_draw.binding(),
                        commit_input.ticket_results,
                        idempotency_key=f"{attempt}:verify-ticket-result-path",
                    )
                    if verified_insertions != 0:
                        raise LegacyReferenceImportError(
                            "atomic ticket results were not already complete"
                        )
                    result_verification_exercised = True
                if stop_requested is not None and stop_requested.is_set():
                    progress = self._repository.progress(run_id)
                    self._repository.append_run_status(
                        run_id,
                        status=ResearchRunStatus.PAUSED,
                        progress_cursor=str(progress.completed_target_count),
                        idempotency_key=f"{attempt}:signal-pause",
                    )
                    paused = self._repository.progress(run_id)
                    return LegacyImportResult(
                        run_id=run_id,
                        status=paused.status,
                        big_lotto_rows=prepared.big_lotto_rows,
                        targets_created=targets_created,
                        tickets_created=tickets_created,
                        results_created=results_created,
                        completed_target_count=paused.completed_target_count,
                        expected_target_count=paused.expected_target_count,
                        deferred_rows=prepared.deferred_rows,
                        duplicate_ticket_rows=prepared.duplicate_ticket_rows,
                        scoring=prepared.scoring,
                        idempotent_no_op=False,
                        interrupted=True,
                        target_duration_ms=tuple(durations),
                        worst_reader_wait_ms=max(reader_waits, default=0.0),
                        elapsed_seconds=time.perf_counter() - started,
                    )
        finally:
            reader_stop.set()
            if reader_thread is not None:
                reader_thread.join(timeout=5)
        if reader_errors:
            raise LegacyReferenceImportError(
                f"reader observation failed: {reader_errors[0]}"
            )

        self._store_summaries(run_id, prepared, attempt=attempt)
        final_before_status = self._repository.progress(run_id)
        if final_before_status.completed_target_count != len(prepared.targets):
            raise LegacyReferenceImportError(
                "import ended without every target becoming visible"
            )
        self._repository.append_run_status(
            run_id,
            status=ResearchRunStatus.COMPLETED,
            progress_cursor=str(final_before_status.completed_target_count),
            idempotency_key=f"{attempt}:completed",
        )
        final = self._repository.progress(run_id)
        return LegacyImportResult(
            run_id=run_id,
            status=final.status,
            big_lotto_rows=prepared.big_lotto_rows,
            targets_created=targets_created,
            tickets_created=tickets_created,
            results_created=results_created,
            completed_target_count=final.completed_target_count,
            expected_target_count=final.expected_target_count,
            deferred_rows=prepared.deferred_rows,
            duplicate_ticket_rows=prepared.duplicate_ticket_rows,
            scoring=prepared.scoring,
            idempotent_no_op=False,
            interrupted=False,
            target_duration_ms=tuple(durations),
            worst_reader_wait_ms=max(reader_waits, default=0.0),
            elapsed_seconds=time.perf_counter() - started,
        )

    def _register_corpus_artifact(
        self,
        evidence: CorpusFileEvidence,
        *,
        attempt: str,
    ) -> str:
        return self._repository.register_artifact(
            artifact_kind="LEGACY_REFERENCE_CORPUS_JSONL",
            source_locator=f"{CORPUS_ROOT_NAME}/{evidence.relative_path}",
            media_type="application/x-ndjson",
            byte_length=evidence.byte_length,
            artifact_sha256=evidence.sha256,
            idempotency_key=f"{attempt}:artifact:{evidence.relative_path}",
        )

    def _completed_target_key_set(
        self,
        run_id: str,
    ) -> set[tuple[str, str, str]]:
        completed: set[tuple[str, str, str]] = set()
        after: CompletedTargetCursor | None = None
        while True:
            page = self._repository.completed_target_keys(
                run_id,
                limit=1_000,
                after=after,
            )
            completed.update(page.items)
            if page.next_cursor is None:
                return completed
            if not isinstance(page.next_cursor, CompletedTargetCursor):
                raise LegacyReferenceImportError(
                    "completed-target pagination returned the wrong cursor type"
                )
            after = page.next_cursor

    def build_target_commit_input(
        self,
        run_id: str,
        prepared: PreparedLegacyCorpus,
        target: LegacyTarget,
    ) -> TargetCommitInput:
        """Build one deterministic atomic target mapping for verification."""

        ticket_count = len(target.rows)
        tickets = tuple(
            TicketInput(
                native_position=row.bet_index,
                ordered_portfolio_position=row.bet_index,
                canonical_ticket_json=_canonical_json(
                    {
                        "main_numbers": list(row.predicted_numbers),
                        "special_numbers": (
                            []
                            if row.predicted_special is None
                            else [row.predicted_special]
                        ),
                    }
                ),
                legacy_record_json=row.raw_record_json,
                legacy_provenance_hash=row.provenance_hash,
                legacy_provenance_source=row.provenance_source,
            )
            for row in target.rows
        )
        results = tuple(
            TicketResultInput(
                ticket_native_position=row.bet_index,
                ticket_count_prefix=ticket_count,
                main_hit_count=row.hit_count,
                special_hit_count=row.special_hit,
                prize_tier_id=None,
                hit_numbers_json=_canonical_json(list(row.hit_numbers)),
                legacy_reported_result_json=_canonical_json(
                    {
                        "actual_numbers": list(row.actual_numbers),
                        "actual_special": row.actual_special,
                        "hit_count": row.hit_count,
                        "hit_numbers": list(row.hit_numbers),
                        "special_hit": row.special_hit,
                    }
                ),
            )
            for row in target.rows
        )
        return TargetCommitInput(
            run_id=run_id,
            strategy_snapshot_id=target.strategy.snapshot_id,
            target_order=target.target_order,
            input_dataset_identity=(
                f"{CORPUS_ROOT_NAME}/{REPLAY_TABLE_RELATIVE_PATH}"
            ),
            input_dataset_sha256=prepared.replay_file.sha256,
            history_cutoff=target.history_cutoff.binding(),
            history_draw_count=target.history_cutoff.history_ordinal,
            source_history_order="draw_date_then_numeric_draw_number",
            target_draw=target.target_draw.binding(),
            causal_eligible=True,
            candidate_k=None,
            combination_count=None,
            ticket_count_prefix=ticket_count,
            tickets=tickets,
            execution_status=ResearchExecutionStatus.OK,
            result_draw=target.target_draw.binding(),
            ticket_results=results,
        )

    def _store_summaries(
        self,
        run_id: str,
        prepared: PreparedLegacyCorpus,
        *,
        attempt: str,
    ) -> None:
        audit = {
            "big_lotto_only": True,
            "big_lotto_rows": prepared.big_lotto_rows,
            "deferred_rows": dict(prepared.deferred_rows),
            "deferred_reason": (
                "POWER_LOTTO and DAILY_539 have no reviewed rule contracts; "
                "deferred to Phase 5"
            ),
            "draws_artifact_sha256": prepared.draws_file.sha256,
            "duplicate_ticket_rows": prepared.duplicate_ticket_rows,
            "legacy_strategy_provenance": (
                "strategy source commit/hash, runtime fingerprint, parameters, "
                "and seed protocol are explicitly LEGACY_UNAVAILABLE; row-level "
                "legacy provenance is retained on each ticket"
            ),
            "replay_artifact_sha256": prepared.replay_file.sha256,
            "scoring_agreements": prepared.scoring.agreements,
            "scoring_disagreements": prepared.scoring.disagreements,
            "scoring_main_hit_agreements": prepared.scoring.main_hit_agreements,
            "scoring_sample_size": prepared.scoring.sample_size,
            "scoring_special_hit_agreements": (
                prepared.scoring.special_hit_agreements
            ),
        }
        self._repository.store_run_summary(
            RunSummaryInput(
                run_id=run_id,
                strategy_snapshot_id=None,
                summary_kind="AUDIT",
                ticket_count_prefix=None,
                summary_version=1,
                denominator_count=prepared.big_lotto_rows,
                successful_count=prepared.big_lotto_rows,
                closed_count=0,
                rank_value=None,
                canonical_summary_json=_canonical_json(audit),
            ),
            idempotency_key=f"{attempt}:summary:audit",
            summary_id=f"{run_id}:summary:audit",
        )
        rows_by_strategy: dict[str, list[LegacyReplayRow]] = defaultdict(list)
        for target in prepared.targets:
            rows_by_strategy[target.strategy.snapshot_id].extend(target.rows)
        for strategy in prepared.strategies:
            rows = rows_by_strategy[strategy.snapshot_id]
            mean_hit_count = sum(row.hit_count for row in rows) / len(rows)
            self._repository.store_run_summary(
                RunSummaryInput(
                    run_id=run_id,
                    strategy_snapshot_id=strategy.snapshot_id,
                    summary_kind="RANKING",
                    ticket_count_prefix=None,
                    summary_version=1,
                    denominator_count=len(rows),
                    successful_count=sum(row.hit_count > 0 for row in rows),
                    closed_count=0,
                    rank_value=mean_hit_count,
                    canonical_summary_json=_canonical_json(
                        {
                            "metric": "legacy_reported_mean_main_hit_count",
                            "row_count": len(rows),
                            "strategy_id": strategy.strategy_id,
                            "strategy_name": strategy.strategy_name,
                            "strategy_version": strategy.strategy_version,
                            "value": mean_hit_count,
                        }
                    ),
                ),
                idempotency_key=(
                    f"{attempt}:summary:ranking:{strategy.snapshot_id}"
                ),
                summary_id=f"{run_id}:summary:ranking:{strategy.snapshot_id}",
            )

    def _observe_reader_wait(
        self,
        run_id: str,
        stop: threading.Event,
        waits: list[float],
        errors: list[BaseException],
    ) -> None:
        while not stop.wait(0.01):
            started = time.perf_counter()
            try:
                self._repository.progress(run_id)
            except BaseException as exc:  # pragma: no cover - surfaced by execute
                errors.append(exc)
                return
            waits.append((time.perf_counter() - started) * 1_000)


def prepare_legacy_corpus(corpus_root: Path) -> PreparedLegacyCorpus:
    """Verify both sealed files before parsing and map BIG_LOTTO rows only."""

    _validate_corpus_root(corpus_root)
    checksums = _load_checksum_manifest(corpus_root)
    replay_file = _verify_corpus_file(
        corpus_root,
        REPLAY_TABLE_RELATIVE_PATH,
        checksums,
    )
    draws_file = _verify_corpus_file(
        corpus_root,
        DRAWS_TABLE_RELATIVE_PATH,
        checksums,
    )
    draws = _load_big_lotto_draws(draws_file)
    rows, deferred = _load_replay_rows(replay_file)
    if len(rows) < SCORING_SAMPLE_SIZE:
        raise LegacyReferenceImportError(
            f"BIG_LOTTO corpus must contain at least {SCORING_SAMPLE_SIZE} rows"
        )
    strategies, targets, duplicate_tickets = _group_targets(
        rows,
        draws,
        replay_file.sha256,
    )
    return PreparedLegacyCorpus(
        replay_file=replay_file,
        draws_file=draws_file,
        targets=targets,
        strategies=strategies,
        big_lotto_rows=len(rows),
        deferred_rows=tuple(sorted(deferred.items())),
        duplicate_ticket_rows=duplicate_tickets,
        scoring=_cross_validate_scoring(rows),
    )


def map_big_lotto_legacy_row(
    raw: Mapping[str, object],
    *,
    raw_record_json: str | None = None,
) -> LegacyReplayRow:
    """Map one BIG_LOTTO row or refuse a deferred lottery with a typed error."""

    lottery_type = _required_text(raw, "lottery_type")
    if lottery_type != _BIG_LOTTO:
        raise UnsupportedLegacyLotteryTypeError(lottery_type)
    status = _required_text(raw, "replay_status")
    if status != "PREDICTED":
        raise LegacyReferenceImportError(
            f"BIG_LOTTO replay_status must be PREDICTED, got {status}"
        )
    predicted_special_raw = raw.get("predicted_special")
    predicted_special = (
        None
        if predicted_special_raw is None
        else _required_int(raw, "predicted_special")
    )
    special_hit = _required_int(raw, "special_hit")
    if special_hit not in (0, 1):
        raise LegacyReferenceImportError("special_hit must be 0 or 1")
    return LegacyReplayRow(
        raw_record_json=raw_record_json or _canonical_json(dict(raw)),
        strategy_id=_required_text(raw, "strategy_id"),
        strategy_name=_required_text(raw, "strategy_name"),
        strategy_version=_required_text(raw, "strategy_version"),
        target_draw=_required_text(raw, "target_draw"),
        target_date=_parse_legacy_date(_required_text(raw, "target_date")).isoformat(),
        history_cutoff_draw=_required_text(raw, "history_cutoff_draw"),
        bet_index=_required_int(raw, "bet_index"),
        predicted_numbers=_number_tuple(raw, "predicted_numbers", expected=6),
        predicted_special=predicted_special,
        actual_numbers=_number_tuple(raw, "actual_numbers", expected=6),
        actual_special=_required_int(raw, "actual_special"),
        hit_numbers=_number_tuple(raw, "hit_numbers", expected=None),
        hit_count=_required_int(raw, "hit_count"),
        special_hit=special_hit,
        provenance_hash=_optional_text(raw, "provenance_hash"),
        provenance_source=_optional_text(raw, "provenance_source"),
    )


def _validate_corpus_root(corpus_root: Path) -> None:
    if not corpus_root.is_absolute() or corpus_root.name != CORPUS_ROOT_NAME:
        raise LegacyReferenceImportError(
            f"corpus root must be an absolute {CORPUS_ROOT_NAME} directory"
        )
    if any(part.casefold() in _FORBIDDEN_PATH_PARTS for part in corpus_root.parts):
        raise LegacyReferenceImportError("corpus root crosses a prohibited path")
    try:
        metadata = os.lstat(corpus_root)
    except OSError as exc:
        raise LegacyReferenceImportError("corpus root is unavailable") from exc
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise LegacyReferenceImportError("corpus root must be a real directory")


def _load_checksum_manifest(corpus_root: Path) -> dict[str, str]:
    checksum_path = corpus_root / "SHA256SUMS"
    _require_regular_file(checksum_path)
    checksums: dict[str, str] = {}
    try:
        with checksum_path.open(encoding="utf-8") as stream:
            for line in stream:
                digest, separator, relative_path = line.rstrip("\n").partition("  ")
                if not separator:
                    raise LegacyReferenceImportError("SHA256SUMS contains an invalid row")
                checksums[relative_path] = digest
    except OSError as exc:
        raise LegacyReferenceImportError("SHA256SUMS could not be read") from exc
    return checksums


def _verify_corpus_file(
    corpus_root: Path,
    relative_path: str,
    checksums: Mapping[str, str],
) -> CorpusFileEvidence:
    expected = checksums.get(relative_path)
    if expected is None:
        raise CorpusChecksumMismatchError(
            f"SHA256SUMS does not seal {relative_path}"
        )
    path = corpus_root / relative_path
    metadata = _require_regular_file(path)
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise LegacyReferenceImportError(
            f"{relative_path} could not be hashed"
        ) from exc
    actual = digest.hexdigest()
    if actual != expected:
        raise CorpusChecksumMismatchError(
            f"{relative_path} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return CorpusFileEvidence(relative_path, path, metadata.st_size, actual)


def _require_regular_file(path: Path) -> os.stat_result:
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise LegacyReferenceImportError(f"missing corpus file: {path.name}") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise LegacyReferenceImportError(f"corpus file is not regular: {path.name}")
    return metadata


def _load_big_lotto_draws(evidence: CorpusFileEvidence) -> dict[str, LegacyDraw]:
    raw_draws: dict[str, tuple[date, tuple[int, ...], int, str]] = {}
    for raw, canonical in _iter_jsonl(evidence.absolute_path):
        if _required_text(raw, "lottery_type") != _BIG_LOTTO:
            continue
        draw_number = _required_text(raw, "draw")
        if draw_number in raw_draws:
            raise LegacyReferenceImportError(
                f"duplicate BIG_LOTTO draw row: {draw_number}"
            )
        draw_date = _parse_legacy_date(_required_text(raw, "date"))
        numbers = _number_tuple(raw, "numbers", expected=6)
        special = _required_int(raw, "special")
        raw_draws[draw_number] = (draw_date, numbers, special, canonical)
    ordered = sorted(
        raw_draws,
        key=lambda draw: (raw_draws[draw][0], int(draw)),
    )
    version = (
        f"{CORPUS_ROOT_NAME}/{DRAWS_TABLE_RELATIVE_PATH}"
        f"@sha256:{evidence.sha256}"
    )
    return {
        draw_number: LegacyDraw(
            draw_number=draw_number,
            draw_date=raw_draws[draw_number][0].isoformat(),
            main_numbers=raw_draws[draw_number][1],
            special_number=raw_draws[draw_number][2],
            draw_sha256=_sha256_text(
                _canonical_json(
                    {
                        "corpus_file_sha256": evidence.sha256,
                        "source_row": json.loads(raw_draws[draw_number][3]),
                    }
                )
            ),
            draw_data_version=version,
            history_ordinal=index,
        )
        for index, draw_number in enumerate(ordered, 1)
    }


def _load_replay_rows(
    evidence: CorpusFileEvidence,
) -> tuple[list[LegacyReplayRow], Counter[str]]:
    rows: list[LegacyReplayRow] = []
    deferred: Counter[str] = Counter()
    for raw, canonical in _iter_jsonl(evidence.absolute_path):
        try:
            rows.append(
                map_big_lotto_legacy_row(raw, raw_record_json=canonical)
            )
        except UnsupportedLegacyLotteryTypeError as exc:
            deferred[exc.lottery_type] += 1
    return rows, deferred


def _group_targets(
    rows: list[LegacyReplayRow],
    draws: Mapping[str, LegacyDraw],
    replay_sha256: str,
) -> tuple[tuple[LegacyStrategy, ...], tuple[LegacyTarget, ...], int]:
    names: dict[tuple[str, str], str] = {}
    grouped: dict[tuple[str, str, str], list[LegacyReplayRow]] = defaultdict(list)
    for row in rows:
        strategy_key = (row.strategy_id, row.strategy_version)
        prior_name = names.setdefault(strategy_key, row.strategy_name)
        if prior_name != row.strategy_name:
            raise LegacyReferenceImportError(
                f"strategy name changed inside corpus: {row.strategy_id}"
            )
        grouped[(*strategy_key, row.target_draw)].append(row)
    strategies = tuple(
        LegacyStrategy(
            strategy_id=strategy_id,
            strategy_name=names[(strategy_id, version)],
            strategy_version=version,
            snapshot_id=_stable_id(
                "strategy-legacy-reference",
                f"{replay_sha256}:{strategy_id}:{version}",
            ),
        )
        for strategy_id, version in sorted(names)
    )
    strategy_by_key = {
        (row.strategy_id, row.strategy_version): row for row in strategies
    }
    groups_by_strategy: dict[tuple[str, str], list[list[LegacyReplayRow]]] = (
        defaultdict(list)
    )
    duplicate_ticket_rows = 0
    for (strategy_id, version, _target_draw), group in grouped.items():
        ordered_rows = sorted(group, key=lambda row: row.bet_index)
        positions = [row.bet_index for row in ordered_rows]
        if positions != list(range(1, len(ordered_rows) + 1)):
            raise LegacyReferenceImportError(
                "bet_index must be unique, contiguous, and start at 1"
            )
        ticket_payloads = [
            (row.predicted_numbers, row.predicted_special) for row in ordered_rows
        ]
        duplicate_ticket_rows += len(ticket_payloads) - len(set(ticket_payloads))
        groups_by_strategy[(strategy_id, version)].append(ordered_rows)

    targets: list[LegacyTarget] = []
    for strategy_key in sorted(groups_by_strategy):
        strategy_groups = sorted(
            groups_by_strategy[strategy_key],
            key=lambda group: (
                date.fromisoformat(group[0].target_date),
                int(group[0].target_draw),
            ),
        )
        for target_order, group in enumerate(strategy_groups):
            first = group[0]
            target_draw = draws.get(first.target_draw)
            cutoff = draws.get(first.history_cutoff_draw)
            if target_draw is None or cutoff is None:
                raise LegacyReferenceImportError(
                    "sealed draws corpus is missing a target or cutoff binding"
                )
            if (
                cutoff.draw_date >= target_draw.draw_date
                or int(cutoff.draw_number) >= int(target_draw.draw_number)
            ):
                raise LegacyCausalCutoffError(
                    f"{first.history_cutoff_draw} is not before {first.target_draw}"
                )
            for row in group:
                if (
                    row.history_cutoff_draw != cutoff.draw_number
                    or row.target_date != target_draw.draw_date
                    or row.actual_numbers != target_draw.main_numbers
                    or row.actual_special != target_draw.special_number
                ):
                    raise LegacyReferenceImportError(
                        "replay rows disagree with their sealed draw bindings"
                    )
            targets.append(
                LegacyTarget(
                    strategy=strategy_by_key[strategy_key],
                    target_order=target_order,
                    history_cutoff=cutoff,
                    target_draw=target_draw,
                    rows=tuple(group),
                )
            )
    targets.sort(
        key=lambda target: (
            target.target_order,
            target.strategy.snapshot_id,
            int(target.target_draw.draw_number),
        )
    )
    return strategies, tuple(targets), duplicate_ticket_rows


def _cross_validate_scoring(
    rows: list[LegacyReplayRow],
) -> LegacyScoringComparison:
    ordered = sorted(
        rows,
        key=lambda row: (
            int(row.target_draw),
            row.strategy_id,
            row.strategy_version,
            row.bet_index,
        ),
    )
    sample = tuple(
        ordered[(index * len(ordered)) // SCORING_SAMPLE_SIZE]
        for index in range(SCORING_SAMPLE_SIZE)
    )
    agreements = 0
    main_hit_agreements = 0
    special_hit_agreements = 0
    examples: list[dict[str, object]] = []
    for row in sample:
        score = score_big_lotto_ticket(
            predicted_main_numbers=row.predicted_numbers,
            winning_main_numbers=row.actual_numbers,
            winning_special_number=row.actual_special,
        )
        main_agrees = score.main_hits == row.hit_count
        special_agrees = int(score.special_hit) == row.special_hit
        main_hit_agreements += int(main_agrees)
        special_hit_agreements += int(special_agrees)
        if main_agrees and special_agrees:
            agreements += 1
        elif len(examples) < 10:
            examples.append(
                {
                    "bet_index": row.bet_index,
                    "legacy_hit_count": row.hit_count,
                    "legacy_special_hit": row.special_hit,
                    "recomputed_hit_count": score.main_hits,
                    "recomputed_special_hit": int(score.special_hit),
                    "strategy_id": row.strategy_id,
                    "target_draw": row.target_draw,
                }
            )
    return LegacyScoringComparison(
        sample_size=len(sample),
        agreements=agreements,
        disagreements=len(sample) - agreements,
        main_hit_agreements=main_hit_agreements,
        special_hit_agreements=special_hit_agreements,
        disagreement_examples=tuple(examples),
    )


def _iter_jsonl(path: Path) -> Iterator[tuple[dict[str, object], str]]:
    try:
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                try:
                    decoded = json.loads(line)
                except (TypeError, ValueError) as exc:
                    raise LegacyReferenceImportError(
                        f"{path.name}:{line_number} is not valid JSON"
                    ) from exc
                if not isinstance(decoded, dict):
                    raise LegacyReferenceImportError(
                        f"{path.name}:{line_number} is not a JSON object"
                    )
                row = cast(dict[str, object], decoded)
                yield row, _canonical_json(row)
    except OSError as exc:
        raise LegacyReferenceImportError(f"{path.name} could not be read") from exc


def _parse_legacy_date(raw: str) -> date:
    normalized = raw.replace("/", "-")
    parts = normalized.split("-")
    if len(parts) != 3:
        raise LegacyReferenceImportError(f"unsupported legacy date: {raw}")
    try:
        return date(*(int(part) for part in parts))
    except ValueError as exc:
        raise LegacyReferenceImportError(f"unsupported legacy date: {raw}") from exc


def _required_text(raw: Mapping[str, object], field: str) -> str:
    value = raw.get(field)
    if type(value) is not str or not value:
        raise LegacyReferenceImportError(f"{field} must be a non-empty string")
    return value


def _optional_text(raw: Mapping[str, object], field: str) -> str | None:
    value = raw.get(field)
    if value is None:
        return None
    if type(value) is not str:
        raise LegacyReferenceImportError(f"{field} must be a string or null")
    return value


def _required_int(raw: Mapping[str, object], field: str) -> int:
    value = raw.get(field)
    if type(value) is not int:
        raise LegacyReferenceImportError(f"{field} must be an integer")
    return value


def _number_tuple(
    raw: Mapping[str, object],
    field: str,
    *,
    expected: int | None,
) -> tuple[int, ...]:
    encoded = raw.get(field)
    if type(encoded) is not str:
        raise LegacyReferenceImportError(f"{field} must contain a JSON array string")
    try:
        decoded = cast(object, json.loads(encoded))
    except (TypeError, ValueError) as exc:
        raise LegacyReferenceImportError(f"{field} is not valid JSON") from exc
    if not isinstance(decoded, list):
        raise LegacyReferenceImportError(f"{field} must contain integer numbers")
    items = cast(list[object], decoded)
    if any(type(item) is not int for item in items):
        raise LegacyReferenceImportError(f"{field} must contain integer numbers")
    numbers = tuple(cast(int, item) for item in items)
    if expected is not None and len(numbers) != expected:
        raise LegacyReferenceImportError(
            f"{field} must contain exactly {expected} numbers"
        )
    return numbers


def _require_commit_oid(value: str) -> None:
    if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        raise LegacyReferenceImportError(
            "source_commit_oid must be the real lowercase Git SHA-1 at import time"
        )


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{_sha256_text(value)}"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


__all__ = [
    "CORPUS_ROOT_NAME",
    "DRAWS_TABLE_RELATIVE_PATH",
    "IMPORTER_IDENTITY",
    "IMPORTER_VERSION",
    "REPLAY_TABLE_RELATIVE_PATH",
    "BigLottoLegacyReferenceImporter",
    "CorpusChecksumMismatchError",
    "LegacyCausalCutoffError",
    "LegacyImportResult",
    "LegacyReferenceImportError",
    "PreparedLegacyCorpus",
    "UnsupportedLegacyLotteryTypeError",
    "map_big_lotto_legacy_row",
    "prepare_legacy_corpus",
]
