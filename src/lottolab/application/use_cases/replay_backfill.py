"""Bounded, resumable replay orchestration over an immutable draw snapshot.

Persistence is a port. No HTTP request launches this worker. Each cell is
committed before the next prediction, so losing the worker loses no completed
cell. The existing replay controller owns ticket completeness and prize rules.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, replace
from datetime import date
from itertools import pairwise
from typing import Any, Protocol

from lottolab.application.use_cases.historical_replay_controller import (
    HistoricalReplayAdapter,
    HistoricalReplayController,
)
from lottolab.domain.historical_replay import (
    HistoricalReplayMode,
    HistoricalReplayRequest,
    ReplayBehavior,
    ReplayDraw,
    ReplayEvaluation,
    ReplaySourceSnapshot,
    ReplayStrategy,
    ReplayTargetRecord,
    ReplayTicket,
)

ENGINE_VERSION = "replay-backfill-v1"
JsonObject = dict[str, Any]


def canonical_json(value: object) -> str:
    """Hash the same JSON representation that is persisted (including key coercion)."""
    normalized = json.loads(json.dumps(value, default=_json_default, allow_nan=False))
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _json_default(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def identity(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


@dataclass(frozen=True)
class BackfillSelection:
    start_date: date | None = None
    end_date: date | None = None
    latest: int | None = None
    all_draws: bool = False

    def __post_init__(self) -> None:
        if self.latest is not None and (type(self.latest) is not int or self.latest < 1):
            raise ValueError("latest must be a positive integer")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not exceed end_date")
        modes = sum(
            (
                self.latest is not None,
                self.all_draws,
                self.start_date is not None or self.end_date is not None,
            )
        )
        if modes != 1:
            raise ValueError("select exactly one of latest, date range, or all draws")

    def select(self, draws: tuple[ReplayDraw, ...]) -> tuple[ReplayDraw, ...]:
        selected = tuple(
            d
            for d in draws
            if (self.start_date is None or d.draw_date >= self.start_date)
            and (self.end_date is None or d.draw_date <= self.end_date)
        )
        if self.latest is not None:
            if len(selected) < self.latest:
                raise ValueError(f"requested {self.latest} targets; only {len(selected)} available")
            selected = selected[-self.latest :]
        if not selected:
            raise ValueError("selection contains no target draws")
        return selected


class BackfillStore(Protocol):
    def prepare(self, manifest: JsonObject) -> None: ...
    def lookup(self, cell_identity: str) -> JsonObject | None: ...
    def lookup_many(self, cell_identities: tuple[str, ...]) -> dict[str, JsonObject]: ...
    def lookup_many_by_unique_keys(
        self,
        keys: tuple[tuple[str, str, str, str, str, str], ...],
    ) -> dict[tuple[str, str, str, str, str, str], JsonObject]: ...
    def lookup_complete_by_logical_keys(
        self,
        keys: tuple[tuple[str, str, str, str], ...],
    ) -> dict[tuple[str, str, str, str], tuple[JsonObject, ...]]: ...
    def save(self, run_id: str, result: JsonObject, *, attempted: bool = True) -> None: ...
    def save_many(self, run_id: str, results: tuple[JsonObject, ...]) -> None: ...
    def summary(self, run_id: str) -> JsonObject: ...


class _OutcomeBlindAdapter:
    """Only the evaluator receives the real target's winning numbers.

    ReplayDraw requires a nonempty number tuple. Zero is an impossible lottery
    number and is an explicit redaction sentinel, never a fabricated outcome.
    Current native adapters consume history only; target-native count resolvers
    still receive the target's public ID/date.
    """

    def __init__(self, adapter: HistoricalReplayAdapter) -> None:
        self._adapter = adapter
        self.lottery_type = adapter.lottery_type

    def generate(
        self, strategy: ReplayStrategy, history: tuple[ReplayDraw, ...], target: ReplayDraw
    ) -> tuple[ReplayTicket, ...]:
        return self._adapter.generate(strategy, history, self._redact(target))

    def expected_native_ticket_count(
        self, strategy: ReplayStrategy, history: tuple[ReplayDraw, ...], target: ReplayDraw
    ) -> int:
        resolver = getattr(self._adapter, "expected_native_ticket_count", None)
        if callable(resolver):
            count = resolver(strategy, history, self._redact(target))
            if type(count) is not int or count < 1:
                raise ValueError("invalid native ticket count")
            return count
        return strategy.native_ticket_count

    def evaluate(
        self, strategy: ReplayStrategy, ticket: ReplayTicket, target: ReplayDraw
    ) -> ReplayEvaluation:
        return self._adapter.evaluate(strategy, ticket, target)

    @staticmethod
    def _redact(target: ReplayDraw) -> ReplayDraw:
        return replace(target, main_numbers=(0,), special_number=None)


class ReplayBackfill:
    def __init__(
        self,
        *,
        adapter: HistoricalReplayAdapter,
        strategies: tuple[ReplayStrategy, ...],
        draws: tuple[ReplayDraw, ...],
        source_identity: str,
        store: BackfillStore,
        execution_version: str,
        source_hash: str | None = None,
        strategy_sources: JsonObject | None = None,
        source_history_provenance_status: str = "UNKNOWN",
    ) -> None:
        if not draws or not strategies or not source_identity or not execution_version:
            raise ValueError("draws, strategies, source and execution identity are required")
        if type(
            source_history_provenance_status
        ) is not str or source_history_provenance_status not in {
            "VERIFIED",
            "UNVERIFIED",
            "UNKNOWN",
        }:
            raise ValueError(
                "source_history_provenance_status must be VERIFIED, UNVERIFIED, or UNKNOWN"
            )
        self.draws = tuple(sorted(draws, key=lambda d: d.sort_key))
        if len({int(d.draw_number) for d in draws}) != len(draws):
            raise ValueError("duplicate numeric draw identity")
        if any(d.lottery_type is not adapter.lottery_type for d in draws):
            raise ValueError("mixed lottery source")
        if len({s.strategy_id for s in strategies}) != len(strategies):
            raise ValueError("duplicate strategy identity")
        if any(s.behavior is ReplayBehavior.LEGACY_NONDETERMINISTIC for s in strategies):
            raise ValueError("unreconstructable stochastic strategies require a pinned seed")
        self.strategies = tuple(sorted(strategies, key=lambda s: s.strategy_id))
        self.lottery_type = adapter.lottery_type
        self.source_identity = source_identity
        self.dataset_identity = identity(
            {"source": source_identity, "draws": [asdict(d) for d in self.draws]}
        )
        self.execution_version = execution_version
        self.source_hash = source_hash or identity({"source_locator": source_identity})
        self.sources = strategy_sources or {}
        self.source_history_provenance_status = source_history_provenance_status
        self.store = store
        self.controller = HistoricalReplayController(_OutcomeBlindAdapter(adapter))

    def manifest(self, selection: BackfillSelection) -> JsonObject:
        targets = selection.select(self.draws)
        manifest: JsonObject = {
            "engine_version": ENGINE_VERSION,
            "execution_version": self.execution_version,
            "lottery_type": self.lottery_type.value,
            "dataset_identity": self.dataset_identity,
            "source_locator": self.source_identity,
            "source_hash": self.source_hash,
            "source_history_provenance_status": self.source_history_provenance_status,
            "strategies": [asdict(s) for s in self.strategies],
            "strategy_sources": self.sources,
            "target_draw_ids": [d.draw_number for d in targets],
            "targets": [
                {
                    "draw_number": draw.draw_number,
                    "draw_date": draw.draw_date.isoformat(),
                    "main_numbers": list(draw.main_numbers),
                    "special_numbers": (
                        [] if draw.special_number is None else [draw.special_number]
                    ),
                    "source_identity": self.dataset_identity,
                }
                for draw in targets
            ],
            "source_targets": [
                {
                    "draw_number": draw.draw_number,
                    "draw_date": draw.draw_date.isoformat(),
                    "main_numbers": list(draw.main_numbers),
                    "special_numbers": (
                        [] if draw.special_number is None else [draw.special_number]
                    ),
                    "source_identity": self.dataset_identity,
                }
                for draw in self.draws
            ],
            "target_draw_count": len(targets),
            "expected_cells": len(targets) * len(self.strategies),
            "selection": asdict(selection),
            "missing_draw_ids": _missing_ids(targets),
        }
        manifest["run_id"] = identity(manifest)
        return json.loads(canonical_json(manifest))

    def execute(
        self,
        selection: BackfillSelection,
        *,
        batch_size: int = 25,
        max_cells: int | None = None,
        retry_failed: bool = False,
        progress: Callable[[JsonObject], None] | None = None,
    ) -> JsonObject:
        if type(batch_size) is not int or batch_size < 1 or batch_size > 250:
            raise ValueError("batch_size must be between 1 and 250")
        if max_cells is not None and (type(max_cells) is not int or max_cells < 1):
            raise ValueError("max_cells must be positive")
        manifest = self.manifest(selection)
        run_id = manifest["run_id"]
        selected = selection.select(self.draws)
        logical_keys = tuple(
            (
                self.lottery_type.value,
                strategy.strategy_id,
                strategy.strategy_version,
                target.draw_number,
            )
            for target in selected
            for strategy in self.strategies
        )
        complete_by_logical_key = self.store.lookup_complete_by_logical_keys(logical_keys)
        for logical_key, previous_results in complete_by_logical_key.items():
            for previous in previous_results:
                previous_execution = previous["execution_version"]
                previous_dataset = previous["dataset_identity"]
                if (
                    previous_execution != self.execution_version
                    or previous_dataset != self.dataset_identity
                ):
                    lottery_type, strategy_id, strategy_version, target_draw_id = logical_key
                    raise ValueError(
                        "COMPLETE replay identity conflict for "
                        f"lottery_type={lottery_type!r}, strategy_id={strategy_id!r}, "
                        f"strategy_version={strategy_version!r}, "
                        f"target_draw_id={target_draw_id!r}: "
                        f"existing execution_version={previous_execution!r}, "
                        f"dataset_identity={previous_dataset!r}; "
                        f"requested execution_version={self.execution_version!r}, "
                        f"dataset_identity={self.dataset_identity!r}; "
                        "refusing unapproved recomputation"
                    )

        # The cross-version guard runs before prepare, because prepare writes a
        # run manifest and target inventory even when no prediction is saved.
        self.store.prepare(manifest)
        executed = 0
        existing_skipped = 0
        draw_positions = {draw.draw_number: index for index, draw in enumerate(self.draws)}
        for batch_start in range(0, len(selected), batch_size):
            batch = selected[batch_start : batch_start + batch_size]
            committed: list[JsonObject] = []
            batch_keys = tuple(
                (
                    self.lottery_type.value,
                    strategy.strategy_id,
                    strategy.strategy_version,
                    self.execution_version,
                    self.dataset_identity,
                    target.draw_number,
                )
                for target in batch
                for strategy in self.strategies
            )
            prior_results = self.store.lookup_many_by_unique_keys(batch_keys)
            for target in batch:
                history = self.draws[: draw_positions[target.draw_number]]
                pending: list[ReplayStrategy] = []
                identities: dict[str, str] = {}
                for strategy in self.strategies:
                    unique_key = (
                        self.lottery_type.value,
                        strategy.strategy_id,
                        strategy.strategy_version,
                        self.execution_version,
                        self.dataset_identity,
                        target.draw_number,
                    )
                    cell_identity = identity(
                        {
                            "execution_version": self.execution_version,
                            "dataset_identity": self.dataset_identity,
                            "lottery_type": self.lottery_type.value,
                            "strategy": asdict(strategy),
                            "target_draw_id": target.draw_number,
                        }
                    )
                    previous = prior_results.get(unique_key)
                    if previous is not None and not (
                        retry_failed and previous["execution_status"] == "FAILED"
                    ):
                        committed.append(previous)
                        existing_skipped += 1
                        continue
                    if max_cells is not None and executed + len(pending) >= max_cells:
                        break
                    identities[strategy.strategy_id] = cell_identity
                    pending.append(strategy)
                if pending:
                    result = self.controller.execute(
                        HistoricalReplayRequest(
                            lottery_type=self.lottery_type,
                            mode=HistoricalReplayMode.INCREMENTAL_REFRESH,
                            source=ReplaySourceSnapshot(self.lottery_type, history, (target,)),
                            strategies=tuple(pending),
                        )
                    )
                    if len(result.records) != len(pending):
                        raise RuntimeError("controller returned an incomplete target batch")
                    committed.extend(
                        self._payload(record, identities[record.strategy.strategy_id])
                        for record in result.records
                    )
                    executed += len(pending)
                if max_cells is not None and executed >= max_cells:
                    break
            if committed:
                self.store.save_many(run_id, tuple(committed))
            if progress is not None and executed:
                progress(self.store.summary(run_id))
            if max_cells is not None and executed >= max_cells:
                break
        summary = self.store.summary(run_id)
        summary["existing_skipped_count"] = existing_skipped
        summary["newly_calculated_count"] = executed
        summary["failed_count"] = summary["failed_cells"]
        if progress is not None:
            progress(summary)
        return summary

    def _cells(
        self, selection: BackfillSelection
    ) -> Iterator[tuple[ReplayDraw, tuple[ReplayDraw, ...], ReplayStrategy]]:
        targets = {d.draw_number for d in selection.select(self.draws)}
        for index, target in enumerate(self.draws):
            if target.draw_number in targets:
                history = self.draws[:index]
                for strategy in self.strategies:
                    yield target, history, strategy

    def _payload(self, record: ReplayTargetRecord, cell_identity: str) -> JsonObject:
        cutoff = record.causal_history[-1] if record.causal_history else None
        source = self.sources.get(record.strategy.strategy_id, {})
        if record.status.value == "COMPLETE":
            hit_details = [
                {"ticket_position": ticket.ticket_position, **asdict(evaluation)}
                for ticket, evaluation in zip(record.tickets, record.evaluations, strict=True)
            ]
        else:
            hit_details = [asdict(evaluation) for evaluation in record.evaluations]
        payload: JsonObject = {
            "cell_identity": cell_identity,
            "engine_version": ENGINE_VERSION,
            "execution_version": self.execution_version,
            "lottery_type": self.lottery_type.value,
            "strategy_id": record.strategy.strategy_id,
            "strategy_version": record.strategy.strategy_version,
            "strategy_fingerprint": record.strategy.fingerprint,
            "strategy_source": source,
            "model_version_or_null": source.get("model_version_or_null"),
            "target_draw_id": record.target.draw_number,
            "target_draw_date": record.target.draw_date.isoformat(),
            "cutoff_draw_id": cutoff.draw_number if cutoff else None,
            "cutoff_draw_date": cutoff.draw_date.isoformat() if cutoff else None,
            "training": {
                "training_status": source.get("training_status", "NOT_TRAINABLE"),
                "model_version": source.get("verified_model_version"),
                "training_cutoff": source.get("verified_training_cutoff"),
                "training_artifact_id": source.get("training_artifact_id"),
            },
            "dataset_identity": self.dataset_identity,
            "source_history_provenance_status": self.source_history_provenance_status,
            "history_fingerprint": record.history_fingerprint,
            "history_count": len(record.causal_history),
            "expected_native_ticket_count": record.expected_native_ticket_count,
            "predicted_tickets": [asdict(t) for t in record.tickets],
            "winning_numbers": {
                "main_numbers": record.target.main_numbers,
                "special_number": record.target.special_number,
            },
            "hit_details": hit_details,
            "prize_results": [e.prize_tier for e in record.evaluations],
            "combination_success": any(e.is_winner for e in record.evaluations)
            if record.status.value == "COMPLETE"
            else None,
            "execution_status": record.status.value,
            "error_reason": record.reason,
        }
        payload["result_identity"] = identity(payload)
        return json.loads(canonical_json(payload))


def _missing_ids(targets: tuple[ReplayDraw, ...]) -> list[str]:
    """Report interior numeric gaps within a ROC issue year, never invent year-end IDs."""
    missing: list[str] = []
    for left, right in pairwise(targets):
        a, b = int(left.draw_number), int(right.draw_number)
        if a // 1_000_000 == b // 1_000_000 and b > a + 1:
            if b - a > 10_000:
                raise ValueError("implausible draw identity gap")
            missing.extend(str(n).zfill(len(left.draw_number)) for n in range(a + 1, b))
    return missing
