"""Immutable projection contracts for persisted Replay-scoring runs.

Pure shapes only: no hashing logic, no SQLite, no re-derivation of scoring or
prize-tier results. Every SHA-256 embedded here is trusted verbatim from the
already-validated source ``ReplayScoringArtifact`` (or its nested records) —
this module only enforces identity completeness and nullable-field
consistency, never recomputes a hash.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)


class ReplayScoringPersistenceOutcome(StrEnum):
    """Typed result of one whole-run persistence attempt."""

    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class ReplayScoringPersistResult:
    """Typed outcome of one :func:`persist_replay_scoring_artifact` attempt."""

    outcome: ReplayScoringPersistenceOutcome
    scoring_artifact_payload_sha256: str

    def __post_init__(self) -> None:
        if type(self.outcome) is not ReplayScoringPersistenceOutcome:
            raise ValueError("outcome must be a ReplayScoringPersistenceOutcome")
        _require_sha256(
            self.scoring_artifact_payload_sha256, "scoring_artifact_payload_sha256"
        )


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{label} must be a non-empty string")


def _require_ordinal(value: object, label: str) -> None:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative exact integer")


def _require_count(value: object, label: str) -> None:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise ValueError(f"{label} must be a non-negative exact integer")


@dataclass(frozen=True, slots=True)
class ReplayScoringRunProjection:
    """One immutable, persisted Replay-scoring run identity."""

    scoring_artifact_schema_version: str
    scoring_artifact_payload_sha256: str
    source_replay_artifact_payload_sha256: str
    dataset_id: str
    dataset_version: str
    lottery_type: str
    target_count: int
    strategy_count: int
    scored_record_count: int
    overall_aggregate_sha256: str

    def __post_init__(self) -> None:
        _require_text(self.scoring_artifact_schema_version, "scoring_artifact_schema_version")
        _require_sha256(self.scoring_artifact_payload_sha256, "scoring_artifact_payload_sha256")
        _require_sha256(
            self.source_replay_artifact_payload_sha256,
            "source_replay_artifact_payload_sha256",
        )
        _require_text(self.dataset_id, "dataset_id")
        _require_text(self.dataset_version, "dataset_version")
        _require_text(self.lottery_type, "lottery_type")
        _require_count(self.target_count, "target_count")
        _require_count(self.strategy_count, "strategy_count")
        _require_count(self.scored_record_count, "scored_record_count")
        if self.scored_record_count != self.target_count * self.strategy_count:
            raise ValueError("scored_record_count must equal target_count times strategy_count")
        _require_sha256(self.overall_aggregate_sha256, "overall_aggregate_sha256")


@dataclass(frozen=True, slots=True)
class ReplayScoredPredictionProjection:
    """One immutable, persisted scored-record row within a run."""

    run_payload_sha256: str
    ordinal: int
    source_snapshot_result_sha256: str
    scored_result_sha256: str
    target_draw_number: str
    target_draw_date: str
    strategy_id: str
    strategy_version: str | None
    source_history_status: str
    source_history_reason_code: str | None
    source_prediction_status: str | None
    source_prediction_reason_code: str | None
    scoring_status: str
    scoring_reason_code: str | None
    predicted_main_numbers: tuple[int, ...] | None
    target_outcome_sha256: str | None
    main_number_hit_count: int | None
    special_number_hit: bool | None
    prize_tier_id: str | None
    prize_official_label: str | None
    no_prize_result: str | None

    def __post_init__(self) -> None:
        _require_sha256(self.run_payload_sha256, "run_payload_sha256")
        _require_ordinal(self.ordinal, "ordinal")
        _require_sha256(self.source_snapshot_result_sha256, "source_snapshot_result_sha256")
        _require_sha256(self.scored_result_sha256, "scored_result_sha256")
        _require_text(self.target_draw_number, "target_draw_number")
        _require_text(self.target_draw_date, "target_draw_date")
        _require_text(self.strategy_id, "strategy_id")
        if self.strategy_version is not None:
            _require_text(self.strategy_version, "strategy_version")
        _require_text(self.source_history_status, "source_history_status")
        if self.source_history_reason_code is not None:
            _require_text(self.source_history_reason_code, "source_history_reason_code")
        if self.source_prediction_status is not None:
            _require_text(self.source_prediction_status, "source_prediction_status")
        if self.source_prediction_reason_code is not None:
            _require_text(
                self.source_prediction_reason_code, "source_prediction_reason_code"
            )
        _require_text(self.scoring_status, "scoring_status")
        if self.scoring_reason_code is not None:
            _require_text(self.scoring_reason_code, "scoring_reason_code")
        if self.predicted_main_numbers is not None and (
            type(self.predicted_main_numbers) is not tuple
            or any(
                type(number) is not int or isinstance(number, bool)
                for number in self.predicted_main_numbers
            )
        ):
            raise ValueError("predicted_main_numbers must be a tuple of exact integers")
        if self.target_outcome_sha256 is not None:
            _require_sha256(self.target_outcome_sha256, "target_outcome_sha256")
        if self.main_number_hit_count is not None and (
            type(self.main_number_hit_count) is not int
            or isinstance(self.main_number_hit_count, bool)
            or self.main_number_hit_count < 0
        ):
            raise ValueError("main_number_hit_count must be a non-negative exact integer")
        if self.special_number_hit is not None and type(self.special_number_hit) is not bool:
            raise ValueError("special_number_hit must be a bool")
        if self.prize_tier_id is not None:
            _require_text(self.prize_tier_id, "prize_tier_id")
        if self.prize_official_label is not None:
            _require_text(self.prize_official_label, "prize_official_label")
        if self.no_prize_result is not None:
            _require_text(self.no_prize_result, "no_prize_result")
        if self.prize_tier_id is not None and self.no_prize_result is not None:
            raise ValueError("a scored record cannot carry both a prize tier and NO_PRIZE")
        if (self.prize_tier_id is None) != (self.prize_official_label is None):
            raise ValueError("prize_tier_id and prize_official_label must be both-or-neither")


@dataclass(frozen=True, slots=True)
class ReplayStrategyAggregateProjection:
    """One immutable, persisted per-strategy aggregate row within a run."""

    run_payload_sha256: str
    ordinal: int
    strategy_id: str
    strategy_version: str | None
    source_snapshot_count: int
    scored_count: int
    history_closed_count: int
    prediction_closed_count: int
    target_outcome_not_found_count: int
    target_identity_mismatch_count: int
    first_prize_count: int
    second_prize_count: int
    third_prize_count: int
    fourth_prize_count: int
    fifth_prize_count: int
    sixth_prize_count: int
    seventh_prize_count: int
    general_prize_count: int
    no_prize_count: int
    aggregate_sha256: str

    def __post_init__(self) -> None:
        _require_sha256(self.run_payload_sha256, "run_payload_sha256")
        _require_ordinal(self.ordinal, "ordinal")
        _require_text(self.strategy_id, "strategy_id")
        if self.strategy_version is not None:
            _require_text(self.strategy_version, "strategy_version")
        for name, value in _aggregate_count_fields(self):
            _require_count(value, name)
        _validate_aggregate_conservation(self)
        _require_sha256(self.aggregate_sha256, "aggregate_sha256")


@dataclass(frozen=True, slots=True)
class ReplayOverallAggregateProjection:
    """One immutable, persisted overall aggregate row within a run (exactly one per run)."""

    run_payload_sha256: str
    source_snapshot_count: int
    scored_count: int
    history_closed_count: int
    prediction_closed_count: int
    target_outcome_not_found_count: int
    target_identity_mismatch_count: int
    first_prize_count: int
    second_prize_count: int
    third_prize_count: int
    fourth_prize_count: int
    fifth_prize_count: int
    sixth_prize_count: int
    seventh_prize_count: int
    general_prize_count: int
    no_prize_count: int
    aggregate_sha256: str

    def __post_init__(self) -> None:
        _require_sha256(self.run_payload_sha256, "run_payload_sha256")
        for name, value in _aggregate_count_fields(self):
            _require_count(value, name)
        _validate_aggregate_conservation(self)
        _require_sha256(self.aggregate_sha256, "aggregate_sha256")


_TIER_COUNT_FIELD_NAMES = (
    "first_prize_count",
    "second_prize_count",
    "third_prize_count",
    "fourth_prize_count",
    "fifth_prize_count",
    "sixth_prize_count",
    "seventh_prize_count",
    "general_prize_count",
)


def _aggregate_count_fields(
    aggregate: ReplayStrategyAggregateProjection | ReplayOverallAggregateProjection,
) -> tuple[tuple[str, int], ...]:
    names = (
        "source_snapshot_count",
        "scored_count",
        "history_closed_count",
        "prediction_closed_count",
        "target_outcome_not_found_count",
        "target_identity_mismatch_count",
        *_TIER_COUNT_FIELD_NAMES,
        "no_prize_count",
    )
    return tuple((name, getattr(aggregate, name)) for name in names)


def _validate_aggregate_conservation(
    aggregate: ReplayStrategyAggregateProjection | ReplayOverallAggregateProjection,
) -> None:
    closed_total = (
        aggregate.history_closed_count
        + aggregate.prediction_closed_count
        + aggregate.target_outcome_not_found_count
        + aggregate.target_identity_mismatch_count
    )
    if aggregate.source_snapshot_count != aggregate.scored_count + closed_total:
        raise ValueError("source snapshot count does not equal scored plus closed counts")
    prize_total = sum(getattr(aggregate, name) for name in _TIER_COUNT_FIELD_NAMES)
    if aggregate.scored_count != prize_total + aggregate.no_prize_count:
        raise ValueError("scored count does not equal prize-tier plus no-prize counts")


__all__ = [
    "ReplayOverallAggregateProjection",
    "ReplayScoredPredictionProjection",
    "ReplayScoringPersistResult",
    "ReplayScoringPersistenceOutcome",
    "ReplayScoringRunProjection",
    "ReplayStrategyAggregateProjection",
]
