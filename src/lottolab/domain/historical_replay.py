"""Shared, lottery-neutral contracts for historical replay orchestration.

The controller deliberately consumes an in-memory source snapshot.  A later
adapter may load that snapshot from a repository, but this domain module does
not know about SQLite, the active historical dataset, or any UI/API surface.
Lottery-specific number validation and prediction semantics remain in the
adapter boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from lottolab.domain.draws import LotteryType


class HistoricalReplayMode(StrEnum):
    INCREMENTAL_REFRESH = "INCREMENTAL_REFRESH"
    RECONCILE = "RECONCILE"
    FULL_REPLAY = "FULL_REPLAY"


class ReplayBehavior(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    SEEDED_STOCHASTIC = "SEEDED_STOCHASTIC"
    LEGACY_NONDETERMINISTIC = "LEGACY_NONDETERMINISTIC"


class ComparisonVerdict(StrEnum):
    NORMAL = "NORMAL"
    REVIEW = "REVIEW"
    ABNORMAL = "ABNORMAL"


class ReplayCellStatus(StrEnum):
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    COMPLETE = "COMPLETE"
    TYPED_CLOSURE = "TYPED_CLOSURE"
    FAILED = "FAILED"
    MISSING = "MISSING"
    PARTIAL = "PARTIAL"


@dataclass(frozen=True, slots=True)
class ReplayDraw:
    """One official draw used as a target or as causal history."""

    lottery_type: LotteryType
    draw_number: str
    draw_date: date
    main_numbers: tuple[int, ...]
    special_number: int | None = None

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if type(self.draw_number) is not str or not self.draw_number:
            raise ValueError("draw_number must be a non-empty string")
        try:
            int(self.draw_number)
        except ValueError as exc:
            raise ValueError("draw_number must contain an integer value") from exc
        if type(self.draw_date) is not date:
            raise ValueError("draw_date must be a date")
        if type(self.main_numbers) is not tuple or not self.main_numbers:
            raise ValueError("main_numbers must be a non-empty tuple")
        if not all(type(number) is int for number in self.main_numbers):
            raise ValueError("main_numbers must contain exact built-in integers")
        if self.special_number is not None and type(self.special_number) is not int:
            raise ValueError("special_number must be an exact built-in integer or None")

    @property
    def sort_key(self) -> tuple[date, int]:
        """Return the canonical date-then-numeric draw ordering."""

        return self.draw_date, int(self.draw_number)


@dataclass(frozen=True, slots=True)
class ReplayStrategy:
    """Pinned identity and replay behavior for one selected strategy."""

    strategy_id: str
    strategy_name: str
    strategy_version: str
    behavior: ReplayBehavior
    native_ticket_count: int
    min_history: int
    fingerprint: str | None = None
    seed_contract: str | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("strategy_id", self.strategy_id),
            ("strategy_name", self.strategy_name),
            ("strategy_version", self.strategy_version),
        ):
            if type(value) is not str or not value.strip():
                raise ValueError(f"{label} must be a non-empty string")
        if type(self.behavior) is not ReplayBehavior:
            raise ValueError("behavior must be a ReplayBehavior")
        if type(self.native_ticket_count) is not int or self.native_ticket_count <= 0:
            raise ValueError("native_ticket_count must be positive")
        if type(self.min_history) is not int or self.min_history < 0:
            raise ValueError("min_history must not be negative")
        if self.fingerprint is not None and (
            type(self.fingerprint) is not str or not self.fingerprint.strip()
        ):
            raise ValueError("fingerprint must be a non-empty string when supplied")
        if self.seed_contract is not None and (
            type(self.seed_contract) is not str or not self.seed_contract.strip()
        ):
            raise ValueError("seed_contract must be a non-empty string when supplied")

    @property
    def identity(self) -> tuple[str, str, str | None]:
        return self.strategy_id, self.strategy_version, self.fingerprint


@dataclass(frozen=True, slots=True)
class ReplayTicket:
    """One native ticket position, retaining lottery-specific second-zone data."""

    ticket_position: int
    main_numbers: tuple[int, ...]
    special_number: int | None = None

    def __post_init__(self) -> None:
        if type(self.ticket_position) is not int or self.ticket_position < 1:
            raise ValueError("ticket_position must be a positive integer")
        if type(self.main_numbers) is not tuple or not self.main_numbers:
            raise ValueError("main_numbers must be a non-empty tuple")
        if not all(type(number) is int for number in self.main_numbers):
            raise ValueError("main_numbers must contain exact built-in integers")
        if self.special_number is not None and type(self.special_number) is not int:
            raise ValueError("special_number must be an exact built-in integer or None")


@dataclass(frozen=True, slots=True)
class ReplayEvaluation:
    """Prize/hit result computed only after a prediction ticket exists."""

    zone1_hits: int
    zone2_hit: bool
    is_winner: bool
    prize_tier: str | None

    def __post_init__(self) -> None:
        if type(self.zone1_hits) is not int or self.zone1_hits < 0:
            raise ValueError("zone1_hits must not be negative")
        if type(self.zone2_hit) is not bool or type(self.is_winner) is not bool:
            raise ValueError("zone2_hit and is_winner must be booleans")
        if self.prize_tier is not None and type(self.prize_tier) is not str:
            raise ValueError("prize_tier must be a string or None")


@dataclass(frozen=True, slots=True)
class ReplayTargetRecord:
    """Candidate-generation result for one target draw and strategy."""

    target: ReplayDraw
    strategy: ReplayStrategy
    status: ReplayCellStatus
    pre_eligible: bool
    causal_history: tuple[ReplayDraw, ...]
    tickets: tuple[ReplayTicket, ...]
    evaluations: tuple[ReplayEvaluation, ...]
    reason: str | None = None
    history_fingerprint: str | None = None
    native_ticket_count: int | None = None

    def __post_init__(self) -> None:
        if type(self.status) is not ReplayCellStatus:
            raise ValueError("status must be a ReplayCellStatus")
        if type(self.pre_eligible) is not bool:
            raise ValueError("pre_eligible must be a boolean")
        if type(self.causal_history) is not tuple:
            raise ValueError("causal_history must be a tuple")
        if type(self.tickets) is not tuple or type(self.evaluations) is not tuple:
            raise ValueError("tickets and evaluations must be tuples")
        if self.native_ticket_count is not None and (
            type(self.native_ticket_count) is not int or self.native_ticket_count <= 0
        ):
            raise ValueError("native_ticket_count must be positive when supplied")
        expected_native_ticket_count = (
            self.native_ticket_count
            if self.native_ticket_count is not None
            else self.strategy.native_ticket_count
        )
        if self.status is ReplayCellStatus.COMPLETE:
            if len(self.tickets) != expected_native_ticket_count:
                raise ValueError("COMPLETE records must preserve every native ticket")
            if len(self.evaluations) != len(self.tickets):
                raise ValueError("COMPLETE records require one evaluation per ticket")
        elif self.evaluations and len(self.evaluations) != len(self.tickets):
            raise ValueError("partial records require aligned ticket/evaluation rows")
        if self.reason is not None and type(self.reason) is not str:
            raise ValueError("reason must be a string or None")

    @property
    def cell_key(self) -> tuple[str, str]:
        return self.target.draw_number, self.strategy.strategy_id

    @property
    def expected_native_ticket_count(self) -> int:
        """Return the target-specific count used for completeness validation."""

        return (
            self.native_ticket_count
            if self.native_ticket_count is not None
            else self.strategy.native_ticket_count
        )


@dataclass(frozen=True, slots=True)
class ReplayStoredTarget:
    """Read-only representation of one existing replay target cell."""

    lottery_type: LotteryType
    target_draw_number: str
    target_draw_date: date
    strategy_id: str
    strategy_version: str
    expected_ticket_count: int
    status: ReplayCellStatus
    cutoff_draw_number: str | None = None
    strategy_fingerprint: str | None = None
    history_fingerprint: str | None = None
    evaluation_complete: bool | None = None

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if type(self.target_draw_number) is not str or not self.target_draw_number:
            raise ValueError("target_draw_number must be a non-empty string")
        if type(self.target_draw_date) is not date:
            raise ValueError("target_draw_date must be a date")
        if type(self.strategy_id) is not str or not self.strategy_id:
            raise ValueError("strategy_id must be a non-empty string")
        if type(self.strategy_version) is not str or not self.strategy_version:
            raise ValueError("strategy_version must be a non-empty string")
        if type(self.expected_ticket_count) is not int or self.expected_ticket_count <= 0:
            raise ValueError("expected_ticket_count must be positive")
        if type(self.status) is not ReplayCellStatus:
            raise ValueError("status must be a ReplayCellStatus")
        if self.cutoff_draw_number is not None and not self.cutoff_draw_number:
            raise ValueError("cutoff_draw_number must be non-empty when supplied")
        if self.evaluation_complete is not None and type(self.evaluation_complete) is not bool:
            raise ValueError("evaluation_complete must be a boolean or None")

    @property
    def cell_key(self) -> tuple[str, str]:
        return self.target_draw_number, self.strategy_id


@dataclass(frozen=True, slots=True)
class ReplayStoredTicket:
    """Read-only representation of one existing native ticket row."""

    lottery_type: LotteryType
    target_draw_number: str
    strategy_id: str
    strategy_version: str
    ticket_position: int
    main_numbers: tuple[int, ...] | None = None
    special_number: int | None = None
    evaluation_target_draw_number: str | None = None

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if type(self.target_draw_number) is not str or not self.target_draw_number:
            raise ValueError("target_draw_number must be a non-empty string")
        if type(self.strategy_id) is not str or not self.strategy_id:
            raise ValueError("strategy_id must be a non-empty string")
        if type(self.strategy_version) is not str or not self.strategy_version:
            raise ValueError("strategy_version must be a non-empty string")
        if type(self.ticket_position) is not int or self.ticket_position < 1:
            raise ValueError("ticket_position must be positive")
        if self.main_numbers is not None:
            if type(self.main_numbers) is not tuple or not self.main_numbers:
                raise ValueError("main_numbers must be a non-empty tuple when supplied")
            if not all(type(number) is int for number in self.main_numbers):
                raise ValueError("main_numbers must contain exact built-in integers")

    @property
    def cell_key(self) -> tuple[str, str]:
        return self.target_draw_number, self.strategy_id


@dataclass(frozen=True, slots=True)
class ReplayRepairCell:
    """One affected target/strategy cell selected for reconciliation repair."""

    target_draw_number: str
    strategy_id: str
    reasons: tuple[str, ...]
    missing_ticket_positions: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not self.target_draw_number or not self.strategy_id:
            raise ValueError("repair cell identity must be non-empty")
        if not self.reasons:
            raise ValueError("repair cell requires at least one reason")
        if any(not reason for reason in self.reasons):
            raise ValueError("repair cell reasons must be non-empty")
        if any(position < 1 for position in self.missing_ticket_positions):
            raise ValueError("missing ticket positions must be positive")


@dataclass(frozen=True, slots=True)
class ReplaySourceSnapshot:
    """Disposable/fake source boundary consumed by the controller."""

    lottery_type: LotteryType
    historical_draws: tuple[ReplayDraw, ...]
    official_draws: tuple[ReplayDraw, ...] = ()
    stored_targets: tuple[ReplayStoredTarget, ...] = ()
    stored_tickets: tuple[ReplayStoredTicket, ...] = ()

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        for label, draws in (
            ("historical_draws", self.historical_draws),
            ("official_draws", self.official_draws),
        ):
            if type(draws) is not tuple:
                raise ValueError(f"{label} must be a tuple")
            if any(draw.lottery_type is not self.lottery_type for draw in draws):
                raise ValueError(f"{label} contains a different lottery type")


@dataclass(frozen=True, slots=True)
class HistoricalReplayRequest:
    """One controller invocation against a pinned disposable source snapshot."""

    lottery_type: LotteryType
    mode: HistoricalReplayMode
    source: ReplaySourceSnapshot
    strategies: tuple[ReplayStrategy, ...]
    cutoff_draw_number: str | None = None

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if type(self.mode) is not HistoricalReplayMode:
            raise ValueError("mode must be a HistoricalReplayMode")
        if self.source.lottery_type is not self.lottery_type:
            raise ValueError("source and request lottery types must match")
        if not self.strategies:
            raise ValueError("strategies must not be empty")
        strategy_ids = [strategy.strategy_id for strategy in self.strategies]
        if len(set(strategy_ids)) != len(strategy_ids):
            raise ValueError("strategies must not contain duplicate strategy ids")
        if any(
            strategy.native_ticket_count < 1 or strategy.min_history < 0
            for strategy in self.strategies
        ):
            raise ValueError("strategy bounds are invalid")
        if self.cutoff_draw_number is not None and not self.cutoff_draw_number:
            raise ValueError("cutoff_draw_number must be non-empty when supplied")


@dataclass(frozen=True, slots=True)
class HistoricalReplayResult:
    """Bounded summary plus candidate records/repair plan for one run."""

    lottery: LotteryType
    mode: HistoricalReplayMode
    historical_start: str | None
    historical_cutoff: str | None
    official_latest: str | None
    strategy_count: int
    target_count: int
    native_ticket_count: int
    expected_native_ticket_count: int
    added_draws: int
    added_strategies: int
    changed_targets: int
    missing_count: int
    partial_count: int
    failed_count: int
    duplicate_count: int
    orphan_count: int
    causal_violation_count: int
    invalid_prize_linkage_count: int
    deterministic_mismatch_count: int
    stochastic_difference_count: int
    strategy_version_change_count: int
    native_ticket_count_change_count: int
    source_correction_count: int
    typed_closure_count: int
    pre_eligible_target_count: int
    comparison_verdict: ComparisonVerdict
    reasons: tuple[str, ...]
    records: tuple[ReplayTargetRecord, ...]
    repair_plan: tuple[ReplayRepairCell, ...]

    def __post_init__(self) -> None:
        counts = (
            self.strategy_count,
            self.target_count,
            self.native_ticket_count,
            self.expected_native_ticket_count,
            self.added_draws,
            self.added_strategies,
            self.changed_targets,
            self.missing_count,
            self.partial_count,
            self.failed_count,
            self.duplicate_count,
            self.orphan_count,
            self.causal_violation_count,
            self.invalid_prize_linkage_count,
            self.deterministic_mismatch_count,
            self.stochastic_difference_count,
            self.strategy_version_change_count,
            self.native_ticket_count_change_count,
            self.source_correction_count,
            self.typed_closure_count,
            self.pre_eligible_target_count,
        )
        if any(type(count) is not int or count < 0 for count in counts):
            raise ValueError("result counts must be non-negative integers")
        if type(self.comparison_verdict) is not ComparisonVerdict:
            raise ValueError("comparison_verdict must be a ComparisonVerdict")
        if type(self.reasons) is not tuple or len(self.reasons) > 8:
            raise ValueError("reasons must contain at most eight bounded strings")
        if any(type(reason) is not str or not reason for reason in self.reasons):
            raise ValueError("reasons must contain non-empty strings")


__all__ = [
    "ComparisonVerdict",
    "HistoricalReplayMode",
    "HistoricalReplayRequest",
    "HistoricalReplayResult",
    "ReplayBehavior",
    "ReplayCellStatus",
    "ReplayDraw",
    "ReplayEvaluation",
    "ReplayRepairCell",
    "ReplaySourceSnapshot",
    "ReplayStoredTarget",
    "ReplayStoredTicket",
    "ReplayStrategy",
    "ReplayTargetRecord",
    "ReplayTicket",
]
