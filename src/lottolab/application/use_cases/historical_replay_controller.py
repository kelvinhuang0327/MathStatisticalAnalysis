"""Reusable three-mode historical replay controller.

The controller owns target selection, causal cutoffs, native-ticket
completeness, comparison classification, and candidate-result accounting.  A
lottery adapter owns prediction and prize semantics.  The source boundary is a
read-only snapshot so ``FULL_REPLAY`` can build a disposable candidate without
ever mutating the active historical dataset.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol

from lottolab.domain.draws import LotteryType
from lottolab.domain.historical_replay import (
    ComparisonVerdict,
    HistoricalReplayMode,
    HistoricalReplayRequest,
    HistoricalReplayResult,
    ReplayBehavior,
    ReplayCellStatus,
    ReplayDraw,
    ReplayEvaluation,
    ReplayRepairCell,
    ReplayStoredTarget,
    ReplayStoredTicket,
    ReplayStrategy,
    ReplayTargetRecord,
    ReplayTicket,
)
from lottolab.strategies.adapters.base import InsufficientHistory, SourceNativePortfolioClosure


class HistoricalReplayAdapter(Protocol):
    """Lottery-specific execution boundary consumed by the shared controller."""

    lottery_type: LotteryType

    def generate(
        self,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        target: ReplayDraw,
    ) -> tuple[ReplayTicket, ...]:
        """Generate the strategy's complete native ticket set."""

        ...

    def evaluate(
        self,
        strategy: ReplayStrategy,
        ticket: ReplayTicket,
        target: ReplayDraw,
    ) -> ReplayEvaluation:
        """Evaluate one generated ticket against its official target draw."""

        ...


class ReplayTypedClosure(Exception):
    """A strategy declared a legitimate native portfolio closure."""


class HistoricalReplayContractError(ValueError):
    """The source snapshot violates the shared controller contract."""


def _new_reasons() -> list[str]:
    return []


def _new_changed_keys() -> set[tuple[str, str]]:
    return set()


def _new_repair_reasons() -> dict[tuple[str, str], set[str]]:
    return {}


def _new_repair_positions() -> dict[tuple[str, str], set[int]]:
    return {}


@dataclass
class _ComparisonAccumulator:
    missing_count: int = 0
    partial_count: int = 0
    failed_count: int = 0
    duplicate_count: int = 0
    orphan_count: int = 0
    causal_violation_count: int = 0
    invalid_prize_linkage_count: int = 0
    deterministic_mismatch_count: int = 0
    stochastic_difference_count: int = 0
    strategy_version_change_count: int = 0
    native_ticket_count_change_count: int = 0
    inconsistent_metadata_count: int = 0
    typed_closure_count: int = 0
    source_correction_count: int = 0
    reasons: list[str] = field(default_factory=_new_reasons)
    changed_keys: set[tuple[str, str]] = field(default_factory=_new_changed_keys)
    repair_reasons: dict[tuple[str, str], set[str]] = field(default_factory=_new_repair_reasons)
    repair_positions: dict[tuple[str, str], set[int]] = field(default_factory=_new_repair_positions)

    def reason(self, value: str) -> None:
        if value and value not in self.reasons:
            self.reasons.append(value)

    def issue(
        self,
        key: tuple[str, str],
        reason: str,
        *,
        missing_positions: Iterable[int] = (),
    ) -> None:
        self.changed_keys.add(key)
        self.repair_reasons.setdefault(key, set()).add(reason)
        self.repair_positions.setdefault(key, set()).update(missing_positions)
        self.reason(reason)

    def verdict(self) -> ComparisonVerdict:
        if any(
            (
                self.missing_count,
                self.partial_count,
                self.failed_count,
                self.duplicate_count,
                self.orphan_count,
                self.causal_violation_count,
                self.invalid_prize_linkage_count,
                self.deterministic_mismatch_count,
                self.inconsistent_metadata_count,
            )
        ):
            return ComparisonVerdict.ABNORMAL
        if any(
            (
                self.strategy_version_change_count,
                self.native_ticket_count_change_count,
                self.source_correction_count,
            )
        ) or "LEGACY_NONDETERMINISTIC_DIFFERENCE_REVIEW" in self.reasons:
            return ComparisonVerdict.REVIEW
        return ComparisonVerdict.NORMAL


class HistoricalReplayController:
    """Run one shared historical replay contract for an injected adapter."""

    def __init__(self, adapter: HistoricalReplayAdapter) -> None:
        lottery_type = getattr(adapter, "lottery_type", None)
        if type(lottery_type) is not LotteryType:
            raise HistoricalReplayContractError(
                "adapter must expose an exact LotteryType lottery_type"
            )
        if lottery_type is LotteryType.BIG_LOTTO:
            raise HistoricalReplayContractError(
                "BIG_LOTTO is a protected deferred integration boundary"
            )
        self._adapter = adapter
        self._lottery_type = lottery_type

    def execute(self, request: HistoricalReplayRequest) -> HistoricalReplayResult:
        """Execute one mode against the request's immutable source snapshot."""

        if request.lottery_type is not self._lottery_type:
            raise HistoricalReplayContractError("request and adapter lottery types differ")

        historical = _ordered_unique_draws(request.source.historical_draws)
        official = _ordered_unique_draws(request.source.official_draws)
        source_correction_count = _source_correction_count(historical, official)
        history_pool = _merge_draws(historical, official)
        targets, historical_cutoff, added_draws = self._select_targets(
            request,
            historical=historical,
            official=official,
        )
        historical_start = historical[0].draw_number if historical else None
        official_latest = official[-1].draw_number if official else None
        accumulator = _ComparisonAccumulator(
            source_correction_count=source_correction_count,
        )
        if source_correction_count:
            accumulator.reason("SOURCE_HISTORICAL_CORRECTION")

        added_strategies = self._compare_strategy_universe(
            request,
            accumulator,
        )

        if request.mode is HistoricalReplayMode.RECONCILE:
            records, expected_native_ticket_count, native_ticket_count = self._reconcile(
                request,
                targets=targets,
                history_pool=history_pool,
                accumulator=accumulator,
            )
        else:
            records, expected_native_ticket_count = self._generate_candidates(
                request,
                targets=targets,
                history_pool=history_pool,
                accumulator=accumulator,
            )
            native_ticket_count = sum(len(record.tickets) for record in records)

        if added_draws:
            accumulator.reason("EXPECTED_NEW_OFFICIAL_DRAWS")
        if added_strategies:
            accumulator.reason("EXPECTED_NEW_STRATEGIES")

        return HistoricalReplayResult(
            lottery=request.lottery_type,
            mode=request.mode,
            historical_start=historical_start,
            historical_cutoff=historical_cutoff,
            official_latest=official_latest,
            strategy_count=len(request.strategies),
            target_count=len(targets),
            native_ticket_count=native_ticket_count,
            expected_native_ticket_count=expected_native_ticket_count,
            added_draws=added_draws,
            added_strategies=added_strategies,
            changed_targets=len(accumulator.changed_keys),
            missing_count=accumulator.missing_count,
            partial_count=accumulator.partial_count,
            failed_count=accumulator.failed_count,
            duplicate_count=accumulator.duplicate_count,
            orphan_count=accumulator.orphan_count,
            causal_violation_count=accumulator.causal_violation_count,
            invalid_prize_linkage_count=accumulator.invalid_prize_linkage_count,
            deterministic_mismatch_count=accumulator.deterministic_mismatch_count,
            stochastic_difference_count=accumulator.stochastic_difference_count,
            strategy_version_change_count=accumulator.strategy_version_change_count,
            native_ticket_count_change_count=accumulator.native_ticket_count_change_count,
            source_correction_count=accumulator.source_correction_count,
            typed_closure_count=accumulator.typed_closure_count,
            pre_eligible_target_count=sum(record.pre_eligible for record in records)
            if request.mode is not HistoricalReplayMode.RECONCILE
            else _count_pre_eligible(targets, history_pool, request.strategies),
            comparison_verdict=accumulator.verdict(),
            reasons=tuple(accumulator.reasons[:8]),
            records=tuple(records),
            repair_plan=_repair_plan(accumulator),
        )

    def _select_targets(
        self,
        request: HistoricalReplayRequest,
        *,
        historical: tuple[ReplayDraw, ...],
        official: tuple[ReplayDraw, ...],
    ) -> tuple[tuple[ReplayDraw, ...], str | None, int]:
        if request.mode is HistoricalReplayMode.INCREMENTAL_REFRESH:
            historical_latest = historical[-1] if historical else None
            if historical_latest is None:
                targets = official
            else:
                targets = tuple(
                    draw for draw in official if draw.sort_key > historical_latest.sort_key
                )
            return (
                targets,
                historical_latest.draw_number if historical_latest else None,
                len(targets),
            )

        if not historical:
            return (), None, 0

        cutoff = _resolve_cutoff(historical, request.cutoff_draw_number)
        assert cutoff is not None
        targets = tuple(draw for draw in historical if draw.sort_key <= cutoff.sort_key)
        return targets, cutoff.draw_number, 0

    def _compare_strategy_universe(
        self,
        request: HistoricalReplayRequest,
        accumulator: _ComparisonAccumulator,
    ) -> int:
        stored_by_id: dict[str, list[ReplayStoredTarget]] = defaultdict(list)
        for stored in request.source.stored_targets:
            if stored.lottery_type is self._lottery_type:
                stored_by_id[stored.strategy_id].append(stored)

        added = 0
        for strategy in request.strategies:
            rows = stored_by_id.get(strategy.strategy_id, [])
            if not rows:
                added += 1
                continue
            if any(
                row.strategy_version != strategy.strategy_version
                or row.strategy_fingerprint != strategy.fingerprint
                for row in rows
            ):
                accumulator.strategy_version_change_count += 1
                accumulator.reason("STRATEGY_IDENTITY_CHANGED")
            if any(row.expected_ticket_count != strategy.native_ticket_count for row in rows):
                accumulator.native_ticket_count_change_count += 1
                accumulator.reason("NATIVE_TICKET_COUNT_CHANGED")
        return added

    def _generate_candidates(
        self,
        request: HistoricalReplayRequest,
        *,
        targets: tuple[ReplayDraw, ...],
        history_pool: tuple[ReplayDraw, ...],
        accumulator: _ComparisonAccumulator,
    ) -> tuple[list[ReplayTargetRecord], int]:
        records: list[ReplayTargetRecord] = []
        expected_native_ticket_count = 0
        for target in targets:
            history = _history_before(history_pool, target)
            for strategy in request.strategies:
                if len(history) >= strategy.min_history:
                    expected_native_ticket_count += strategy.native_ticket_count
                record = self._generate_cell(strategy, target, history)
                records.append(record)
                self._record_generation_outcome(record, accumulator)
        return records, expected_native_ticket_count

    def _generate_cell(
        self,
        strategy: ReplayStrategy,
        target: ReplayDraw,
        history: tuple[ReplayDraw, ...],
    ) -> ReplayTargetRecord:
        history_fingerprint = _history_fingerprint(history)
        if any(row.sort_key >= target.sort_key for row in history):
            return _empty_record(
                target,
                strategy,
                ReplayCellStatus.FAILED,
                history,
                "CAUSAL_CUTOFF_VIOLATION",
                history_fingerprint,
            )
        if len(history) < strategy.min_history:
            return _empty_record(
                target,
                strategy,
                ReplayCellStatus.NOT_ELIGIBLE,
                history,
                f"INSUFFICIENT_CAUSAL_HISTORY_REQUIRED_{strategy.min_history}_GOT_{len(history)}",
                history_fingerprint,
            )

        try:
            tickets = self._adapter.generate(strategy, history, target)
        except (ReplayTypedClosure, SourceNativePortfolioClosure) as exc:
            return _empty_record(
                target,
                strategy,
                ReplayCellStatus.TYPED_CLOSURE,
                history,
                f"{type(exc).__name__}: {_short_message(exc)}",
                history_fingerprint,
                pre_eligible=True,
            )
        except InsufficientHistory as exc:
            return _empty_record(
                target,
                strategy,
                ReplayCellStatus.NOT_ELIGIBLE,
                history,
                f"{type(exc).__name__}: {_short_message(exc)}",
                history_fingerprint,
            )
        except Exception as exc:  # Adapter failures are recorded, never hidden.
            return _empty_record(
                target,
                strategy,
                ReplayCellStatus.FAILED,
                history,
                f"FAILED_EXECUTION: {type(exc).__name__}: {_short_message(exc)}",
                history_fingerprint,
                pre_eligible=True,
            )

        if type(tickets) is not tuple or len(tickets) != strategy.native_ticket_count:
            return _empty_record(
                target,
                strategy,
                ReplayCellStatus.FAILED,
                history,
                "NATIVE_TICKET_COUNT_MISMATCH",
                history_fingerprint,
                pre_eligible=True,
            )
        positions = tuple(ticket.ticket_position for ticket in tickets)
        expected_positions = tuple(range(1, strategy.native_ticket_count + 1))
        if positions != expected_positions:
            return _empty_record(
                target,
                strategy,
                ReplayCellStatus.FAILED,
                history,
                "NATIVE_TICKET_POSITION_INCOMPLETE",
                history_fingerprint,
                pre_eligible=True,
            )

        evaluations: list[ReplayEvaluation] = []
        try:
            for ticket in tickets:
                evaluation = self._adapter.evaluate(strategy, ticket, target)
                if type(evaluation) is not ReplayEvaluation:
                    raise TypeError("adapter evaluation must be a ReplayEvaluation")
                evaluations.append(evaluation)
        except Exception as exc:  # Evaluation is intentionally after generation.
            return _empty_record(
                target,
                strategy,
                ReplayCellStatus.FAILED,
                history,
                f"INVALID_PRIZE_RESULT_LINKAGE: {type(exc).__name__}: {_short_message(exc)}",
                history_fingerprint,
                pre_eligible=True,
            )

        return ReplayTargetRecord(
            target=target,
            strategy=strategy,
            status=ReplayCellStatus.COMPLETE,
            pre_eligible=True,
            causal_history=history,
            tickets=tickets,
            evaluations=tuple(evaluations),
            history_fingerprint=history_fingerprint,
        )

    @staticmethod
    def _record_generation_outcome(
        record: ReplayTargetRecord,
        accumulator: _ComparisonAccumulator,
    ) -> None:
        if record.status is ReplayCellStatus.TYPED_CLOSURE:
            accumulator.typed_closure_count += 1
            accumulator.reason("DECLARED_NATIVE_TICKET_CLOSURE")
        elif record.status is ReplayCellStatus.FAILED:
            accumulator.failed_count += 1
            accumulator.issue(record.cell_key, "FAILED_TARGET")
            if record.reason == "CAUSAL_CUTOFF_VIOLATION":
                accumulator.causal_violation_count += 1
                accumulator.reason("CAUSAL_CUTOFF_VIOLATION")
            if record.reason is not None and record.reason.startswith(
                "INVALID_PRIZE_RESULT_LINKAGE"
            ):
                accumulator.invalid_prize_linkage_count += 1
                accumulator.reason("INVALID_PRIZE_RESULT_LINKAGE")

    def _reconcile(
        self,
        request: HistoricalReplayRequest,
        *,
        targets: tuple[ReplayDraw, ...],
        history_pool: tuple[ReplayDraw, ...],
        accumulator: _ComparisonAccumulator,
    ) -> tuple[list[ReplayTargetRecord], int, int]:
        eligible_keys: dict[
            tuple[str, str], tuple[ReplayDraw, ReplayStrategy, tuple[ReplayDraw, ...]]
        ] = {}
        all_keys: set[tuple[str, str]] = set()
        expected_native_ticket_count = 0
        for target in targets:
            history = _history_before(history_pool, target)
            for strategy in request.strategies:
                key = (target.draw_number, strategy.strategy_id)
                all_keys.add(key)
                if len(history) >= strategy.min_history:
                    eligible_keys[key] = (target, strategy, history)
                    expected_native_ticket_count += strategy.native_ticket_count

        targets_by_key: dict[tuple[str, str], list[ReplayStoredTarget]] = defaultdict(list)
        for stored in request.source.stored_targets:
            key = stored.cell_key
            if stored.lottery_type is self._lottery_type:
                targets_by_key[key].append(stored)
            else:
                accumulator.orphan_count += 1
                accumulator.reason("ORPHAN_TARGET")

        tickets_by_key: dict[tuple[str, str], list[ReplayStoredTicket]] = defaultdict(list)
        for stored_ticket in request.source.stored_tickets:
            key = stored_ticket.cell_key
            if stored_ticket.lottery_type is self._lottery_type:
                tickets_by_key[key].append(stored_ticket)
            else:
                accumulator.orphan_count += 1
                accumulator.reason("ORPHAN_TICKET")

        issue_records: dict[tuple[str, str], ReplayTargetRecord] = {}
        for key, (target, strategy, history) in eligible_keys.items():
            rows = targets_by_key.get(key, [])
            tickets = tickets_by_key.get(key, [])
            if len(rows) > 1:
                accumulator.duplicate_count += len(rows) - 1
                accumulator.issue(key, "DUPLICATE_TARGET")
            row = rows[0] if rows else None
            positions = [ticket.ticket_position for ticket in tickets]
            duplicate_positions = len(positions) - len(set(positions))
            if duplicate_positions:
                accumulator.duplicate_count += duplicate_positions
                accumulator.issue(key, "DUPLICATE_TICKET")

            cell_reasons: set[str] = set()
            missing_positions: set[int] = set()
            if row is None:
                accumulator.missing_count += 1
                cell_reasons.add("MISSING_ELIGIBLE_TARGET")
                missing_positions.update(range(1, strategy.native_ticket_count + 1))
            else:
                if row.target_draw_date != target.draw_date:
                    cell_reasons.add("INCONSISTENT_TARGET_METADATA")
                if row.strategy_version != strategy.strategy_version or (
                    row.strategy_fingerprint != strategy.fingerprint
                ):
                    cell_reasons.add("STRATEGY_IDENTITY_CHANGED")
                if row.expected_ticket_count != strategy.native_ticket_count:
                    cell_reasons.add("NATIVE_TICKET_COUNT_CHANGED")
                if row.cutoff_draw_number is not None and _draw_number_at_or_after(
                    history_pool, row.cutoff_draw_number, target
                ):
                    accumulator.causal_violation_count += 1
                    cell_reasons.add("CAUSAL_CUTOFF_VIOLATION")
                if row.history_fingerprint is not None and row.history_fingerprint != (
                    _history_fingerprint(history)
                ):
                    accumulator.source_correction_count += 1
                    cell_reasons.add("SOURCE_HISTORICAL_CORRECTION")
                if row.status is ReplayCellStatus.FAILED:
                    accumulator.failed_count += 1
                    cell_reasons.add("FAILED_TARGET")
                elif row.status is ReplayCellStatus.TYPED_CLOSURE:
                    accumulator.typed_closure_count += 1
                elif row.status is ReplayCellStatus.PARTIAL:
                    accumulator.partial_count += 1
                    cell_reasons.add("PARTIAL_TARGET")
                elif row.status is ReplayCellStatus.NOT_ELIGIBLE:
                    accumulator.missing_count += 1
                    cell_reasons.add("MISSING_ELIGIBLE_TARGET")

                missing_positions.update(
                    position
                    for position in range(1, strategy.native_ticket_count + 1)
                    if position not in positions
                )
                if row.status is ReplayCellStatus.COMPLETE and missing_positions:
                    accumulator.partial_count += 1
                    cell_reasons.add("MISSING_NATIVE_TICKET_POSITION")
                if row.evaluation_complete is False and row.status is ReplayCellStatus.COMPLETE:
                    accumulator.invalid_prize_linkage_count += 1
                    cell_reasons.add("INVALID_PRIZE_RESULT_LINKAGE")

            if tickets and row is None:
                accumulator.orphan_count += len(tickets)
                cell_reasons.add("ORPHAN_TICKET")
            elif tickets:
                for stored_ticket in tickets:
                    if stored_ticket.evaluation_target_draw_number is not None and (
                        stored_ticket.evaluation_target_draw_number != target.draw_number
                    ):
                        accumulator.invalid_prize_linkage_count += 1
                        cell_reasons.add("INVALID_PRIZE_RESULT_LINKAGE")

            for reason in sorted(cell_reasons):
                accumulator.issue(key, reason, missing_positions=missing_positions)
                if reason == "STRATEGY_IDENTITY_CHANGED":
                    accumulator.strategy_version_change_count += 1
                    accumulator.reason("STRATEGY_IDENTITY_CHANGED")
                elif reason == "NATIVE_TICKET_COUNT_CHANGED":
                    accumulator.native_ticket_count_change_count += 1
                    accumulator.reason("NATIVE_TICKET_COUNT_CHANGED")
                elif reason == "INCONSISTENT_TARGET_METADATA":
                    accumulator.inconsistent_metadata_count += 1
                    accumulator.reason("INCONSISTENT_TARGET_METADATA")
                elif reason == "SOURCE_HISTORICAL_CORRECTION":
                    accumulator.reason("SOURCE_HISTORICAL_CORRECTION")
                elif reason == "CAUSAL_CUTOFF_VIOLATION":
                    accumulator.reason("CAUSAL_CUTOFF_VIOLATION")
                elif reason == "INVALID_PRIZE_RESULT_LINKAGE":
                    accumulator.reason("INVALID_PRIZE_RESULT_LINKAGE")

            if cell_reasons:
                status = (
                    ReplayCellStatus.MISSING
                    if "MISSING_ELIGIBLE_TARGET" in cell_reasons
                    and len(cell_reasons) == 1
                    else ReplayCellStatus.FAILED
                    if "FAILED_TARGET" in cell_reasons
                    else ReplayCellStatus.PARTIAL
                )
                issue_records[key] = ReplayTargetRecord(
                    target=target,
                    strategy=strategy,
                    status=status,
                    pre_eligible=True,
                    causal_history=history,
                    tickets=(),
                    evaluations=(),
                    reason=";".join(sorted(cell_reasons)),
                    history_fingerprint=_history_fingerprint(history),
                )

            self._compare_stored_output(
                request,
                target=target,
                strategy=strategy,
                history=history,
                stored_target=row,
                stored_tickets=tickets,
                accumulator=accumulator,
            )

        for key, rows in targets_by_key.items():
            if key not in all_keys:
                accumulator.orphan_count += len(rows)
                accumulator.issue(key, "ORPHAN_TARGET")
                accumulator.reason("ORPHAN_TARGET")
        for key, tickets in tickets_by_key.items():
            if key not in all_keys or key not in eligible_keys:
                accumulator.orphan_count += len(tickets)
                accumulator.issue(key, "ORPHAN_TICKET")
                accumulator.reason("ORPHAN_TICKET")

        native_ticket_count = sum(
            1
            for key, tickets in tickets_by_key.items()
            if key in eligible_keys
            for _ticket in tickets
        )
        return (
            [issue_records[key] for key in sorted(issue_records)],
            expected_native_ticket_count,
            native_ticket_count,
        )

    def _compare_stored_output(
        self,
        request: HistoricalReplayRequest,
        *,
        target: ReplayDraw,
        strategy: ReplayStrategy,
        history: tuple[ReplayDraw, ...],
        stored_target: ReplayStoredTarget | None,
        stored_tickets: list[ReplayStoredTicket],
        accumulator: _ComparisonAccumulator,
    ) -> None:
        if stored_target is None or stored_target.status is not ReplayCellStatus.COMPLETE:
            return
        if not stored_tickets or any(ticket.main_numbers is None for ticket in stored_tickets):
            return
        if len(stored_tickets) != strategy.native_ticket_count:
            return

        current = self._generate_cell(strategy, target, history)
        if current.status is ReplayCellStatus.FAILED:
            accumulator.failed_count += 1
            accumulator.issue(current.cell_key, "FAILED_TARGET")
            return
        if current.status is not ReplayCellStatus.COMPLETE:
            return

        stored_signature = tuple(
            (ticket.ticket_position, ticket.main_numbers, ticket.special_number)
            for ticket in sorted(stored_tickets, key=lambda item: item.ticket_position)
        )
        current_signature = tuple(
            (ticket.ticket_position, ticket.main_numbers, ticket.special_number)
            for ticket in current.tickets
        )
        if stored_signature == current_signature:
            return

        accumulator.changed_keys.add(current.cell_key)
        if strategy.behavior is ReplayBehavior.DETERMINISTIC:
            accumulator.deterministic_mismatch_count += 1
            accumulator.issue(current.cell_key, "DETERMINISTIC_OUTPUT_MISMATCH")
            accumulator.reason("DETERMINISTIC_OUTPUT_MISMATCH")
        elif strategy.behavior is ReplayBehavior.SEEDED_STOCHASTIC:
            accumulator.stochastic_difference_count += 1
            accumulator.reason("SEEDED_STOCHASTIC_DIFFERENCE_ALLOWED")
        else:
            accumulator.stochastic_difference_count += 1
            accumulator.repair_reasons.setdefault(current.cell_key, set()).add(
                "LEGACY_NONDETERMINISTIC_DIFFERENCE_REVIEW"
            )
            accumulator.reason("LEGACY_NONDETERMINISTIC_DIFFERENCE_REVIEW")


def _empty_record(
    target: ReplayDraw,
    strategy: ReplayStrategy,
    status: ReplayCellStatus,
    history: tuple[ReplayDraw, ...],
    reason: str,
    history_fingerprint: str | None,
    *,
    pre_eligible: bool = False,
) -> ReplayTargetRecord:
    return ReplayTargetRecord(
        target=target,
        strategy=strategy,
        status=status,
        pre_eligible=pre_eligible,
        causal_history=history,
        tickets=(),
        evaluations=(),
        reason=reason,
        history_fingerprint=history_fingerprint,
    )


def _ordered_unique_draws(draws: tuple[ReplayDraw, ...]) -> tuple[ReplayDraw, ...]:
    by_number: dict[str, ReplayDraw] = {}
    for draw in draws:
        by_number[draw.draw_number] = draw
    return tuple(sorted(by_number.values(), key=lambda draw: draw.sort_key))


def _merge_draws(
    historical: tuple[ReplayDraw, ...],
    official: tuple[ReplayDraw, ...],
) -> tuple[ReplayDraw, ...]:
    by_number = {draw.draw_number: draw for draw in historical}
    by_number.update({draw.draw_number: draw for draw in official})
    return tuple(sorted(by_number.values(), key=lambda draw: draw.sort_key))


def _source_correction_count(
    historical: tuple[ReplayDraw, ...],
    official: tuple[ReplayDraw, ...],
) -> int:
    historical_by_number = {draw.draw_number: draw for draw in historical}
    return sum(
        1
        for draw in official
        if draw.draw_number in historical_by_number
        and draw != historical_by_number[draw.draw_number]
    )


def _resolve_cutoff(
    draws: tuple[ReplayDraw, ...], cutoff_draw_number: str | None
) -> ReplayDraw | None:
    if not draws:
        return None
    if cutoff_draw_number is None:
        return draws[-1]
    for draw in draws:
        if draw.draw_number == cutoff_draw_number:
            return draw
    raise HistoricalReplayContractError(
        f"pinned cutoff draw {cutoff_draw_number!r} is absent from historical source"
    )


def _history_before(
    draws: tuple[ReplayDraw, ...], target: ReplayDraw
) -> tuple[ReplayDraw, ...]:
    return tuple(draw for draw in draws if draw.sort_key < target.sort_key)


def _history_fingerprint(history: tuple[ReplayDraw, ...]) -> str:
    payload = [
        {
            "draw_number": draw.draw_number,
            "draw_date": draw.draw_date.isoformat(),
            "lottery_type": draw.lottery_type.value,
            "main_numbers": draw.main_numbers,
            "special_number": draw.special_number,
        }
        for draw in history
    ]
    canonical = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _draw_number_at_or_after(
    history_pool: tuple[ReplayDraw, ...], cutoff_draw_number: str, target: ReplayDraw
) -> bool:
    cutoff = next(
        (draw for draw in history_pool if draw.draw_number == cutoff_draw_number),
        None,
    )
    return cutoff is None or cutoff.sort_key >= target.sort_key


def _count_pre_eligible(
    targets: tuple[ReplayDraw, ...],
    history_pool: tuple[ReplayDraw, ...],
    strategies: tuple[ReplayStrategy, ...],
) -> int:
    return sum(
        len(_history_before(history_pool, target)) >= strategy.min_history
        for target in targets
        for strategy in strategies
    )


def _repair_plan(accumulator: _ComparisonAccumulator) -> tuple[ReplayRepairCell, ...]:
    return tuple(
        ReplayRepairCell(
            target_draw_number=target_draw_number,
            strategy_id=strategy_id,
            reasons=tuple(sorted(accumulator.repair_reasons[(target_draw_number, strategy_id)])),
            missing_ticket_positions=tuple(
                sorted(
                    accumulator.repair_positions.get((target_draw_number, strategy_id), set())
                )
            ),
        )
        for target_draw_number, strategy_id in sorted(accumulator.repair_reasons)
    )


def _short_message(exc: Exception) -> str:
    message = str(exc).replace("\n", " ").strip()
    return message[:240] if message else "no detail"


__all__ = [
    "HistoricalReplayAdapter",
    "HistoricalReplayContractError",
    "HistoricalReplayController",
    "ReplayTypedClosure",
]
