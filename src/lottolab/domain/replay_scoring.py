"""Immutable, deterministic contracts for post-hoc Replay prize scoring.

This module owns shapes and invariants only.  It never loads target outcomes,
executes a strategy, or persists a scoring artifact.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields
from datetime import date
from enum import StrEnum
from typing import Any

from lottolab.domain.draws import LotteryType
from lottolab.domain.lottery_rules import (
    BIG_LOTTO_RULE_CONTRACT,
    BigLottoPrizeTierId,
    NoPrizeResult,
)

TARGET_OUTCOME_SCHEMA_VERSION = "1.0.0"
SCORING_SCHEMA_VERSION = "1.0.0"
AGGREGATION_SCHEMA_VERSION = "1.0.0"

_SHA256 = re.compile(r"[0-9a-f]{64}", flags=re.ASCII)
_NORMALIZED_DRAW_NUMBER = re.compile(r"[0-9]{1,32}", flags=re.ASCII)


class ReplayScoringStatus(StrEnum):
    SCORED = "SCORED"
    NOT_SCORED_HISTORY_CLOSED = "NOT_SCORED_HISTORY_CLOSED"
    NOT_SCORED_PREDICTION_CLOSED = "NOT_SCORED_PREDICTION_CLOSED"
    TARGET_OUTCOME_NOT_FOUND = "TARGET_OUTCOME_NOT_FOUND"
    TARGET_IDENTITY_MISMATCH = "TARGET_IDENTITY_MISMATCH"


class ReplayScoringReason(StrEnum):
    SOURCE_HISTORY_CLOSED = "SOURCE_HISTORY_CLOSED"
    SOURCE_PREDICTION_CLOSED = "SOURCE_PREDICTION_CLOSED"
    TARGET_OUTCOME_NOT_FOUND = "TARGET_OUTCOME_NOT_FOUND"
    TARGET_OUTCOME_STORAGE_UNAVAILABLE = "TARGET_OUTCOME_STORAGE_UNAVAILABLE"
    TARGET_IDENTITY_MISMATCH = "TARGET_IDENTITY_MISMATCH"


class ReplayTargetOutcomeReadStatus(StrEnum):
    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"


class ReplayTargetOutcomeReadReason(StrEnum):
    TARGET_OUTCOME_NOT_FOUND = "TARGET_OUTCOME_NOT_FOUND"
    TARGET_OUTCOME_STORAGE_UNAVAILABLE = "TARGET_OUTCOME_STORAGE_UNAVAILABLE"


def _canonical_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value:
        raise ValueError(f"{label} must be a non-empty string")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def validate_replay_target_draw_number(value: object) -> None:
    """Require the canonical persisted/API draw-number identity shape.

    Leading zeroes remain significant; normalization rejects rather than
    rewriting whitespace, Unicode decimal digits, or overlong identifiers.
    """

    if type(value) is not str or _NORMALIZED_DRAW_NUMBER.fullmatch(value) is None:
        raise ValueError("target_draw_number must contain 1-32 ASCII decimal digits")


def _validate_main_numbers(numbers: tuple[int, ...], label: str) -> None:
    rule = BIG_LOTTO_RULE_CONTRACT
    if type(numbers) is not tuple:
        raise ValueError(f"{label} must be a tuple")
    if len(numbers) != rule.main_number_count:
        raise ValueError(f"{label} must contain exactly {rule.main_number_count} numbers")
    if any(type(number) is not int for number in numbers):
        raise ValueError(f"{label} must contain exact built-in integers")
    if any(not rule.main_number_min <= number <= rule.main_number_max for number in numbers):
        raise ValueError(
            f"{label} values must fall within "
            f"[{rule.main_number_min}..{rule.main_number_max}]"
        )
    if len(set(numbers)) != len(numbers):
        raise ValueError(f"{label} must not contain duplicates")
    if numbers != tuple(sorted(numbers)):
        raise ValueError(f"{label} must use canonical ascending order")


@dataclass(frozen=True, slots=True)
class ReplayTargetOutcome:
    outcome_schema_version: str
    lottery_type: LotteryType
    target_draw_number: str
    target_draw_date: date
    winning_main_numbers: tuple[int, ...]
    winning_special_number: int
    outcome_sha256: str

    def __post_init__(self) -> None:
        if self.outcome_schema_version != TARGET_OUTCOME_SCHEMA_VERSION:
            raise ValueError("unsupported outcome_schema_version")
        if self.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("Replay prize scoring currently supports BIG_LOTTO only")
        validate_replay_target_draw_number(self.target_draw_number)
        if type(self.target_draw_date) is not date:
            raise ValueError("target_draw_date must be a date")
        _validate_main_numbers(self.winning_main_numbers, "winning_main_numbers")
        rule = BIG_LOTTO_RULE_CONTRACT
        if type(self.winning_special_number) is not int:
            raise ValueError("winning_special_number must be an exact built-in integer")
        if not rule.special_number_min <= self.winning_special_number <= rule.special_number_max:
            raise ValueError(
                "winning_special_number must fall within "
                f"[{rule.special_number_min}..{rule.special_number_max}]"
            )
        if self.winning_special_number in self.winning_main_numbers:
            raise ValueError("winning_special_number must not overlap winning_main_numbers")
        _require_sha256(self.outcome_sha256, "outcome_sha256")
        if self.outcome_sha256 != recompute_target_outcome_sha256(self):
            raise ValueError("outcome_sha256 does not match target outcome content")

    @classmethod
    def create(
        cls,
        *,
        lottery_type: LotteryType,
        target_draw_number: str,
        target_draw_date: date,
        winning_main_numbers: tuple[int, ...],
        winning_special_number: int,
    ) -> ReplayTargetOutcome:
        payload = _target_outcome_payload(
            outcome_schema_version=TARGET_OUTCOME_SCHEMA_VERSION,
            lottery_type=lottery_type,
            target_draw_number=target_draw_number,
            target_draw_date=target_draw_date,
            winning_main_numbers=winning_main_numbers,
            winning_special_number=winning_special_number,
        )
        return cls(
            outcome_schema_version=TARGET_OUTCOME_SCHEMA_VERSION,
            lottery_type=lottery_type,
            target_draw_number=target_draw_number,
            target_draw_date=target_draw_date,
            winning_main_numbers=winning_main_numbers,
            winning_special_number=winning_special_number,
            outcome_sha256=_canonical_sha256(payload),
        )


def _target_outcome_payload(
    *,
    outcome_schema_version: str,
    lottery_type: LotteryType,
    target_draw_number: str,
    target_draw_date: date,
    winning_main_numbers: tuple[int, ...],
    winning_special_number: int,
) -> dict[str, Any]:
    return {
        "lottery_type": lottery_type.value,
        "outcome_schema_version": outcome_schema_version,
        "target_draw_date": target_draw_date.isoformat(),
        "target_draw_number": target_draw_number,
        "winning_main_numbers": list(winning_main_numbers),
        "winning_special_number": winning_special_number,
    }


def recompute_target_outcome_sha256(outcome: ReplayTargetOutcome) -> str:
    return _canonical_sha256(
        _target_outcome_payload(
            outcome_schema_version=outcome.outcome_schema_version,
            lottery_type=outcome.lottery_type,
            target_draw_number=outcome.target_draw_number,
            target_draw_date=outcome.target_draw_date,
            winning_main_numbers=outcome.winning_main_numbers,
            winning_special_number=outcome.winning_special_number,
        )
    )


@dataclass(frozen=True, slots=True)
class ReplayTargetOutcomeReadResult:
    status: ReplayTargetOutcomeReadStatus
    outcome: ReplayTargetOutcome | None
    reason_code: ReplayTargetOutcomeReadReason | None

    def __post_init__(self) -> None:
        if self.status is ReplayTargetOutcomeReadStatus.FOUND:
            if self.outcome is None or self.reason_code is not None:
                raise ValueError("FOUND requires an outcome and no reason_code")
        elif self.outcome is not None or self.reason_code is None:
            raise ValueError("NOT_FOUND requires a reason_code and no outcome")

    @classmethod
    def found(cls, outcome: ReplayTargetOutcome) -> ReplayTargetOutcomeReadResult:
        return cls(ReplayTargetOutcomeReadStatus.FOUND, outcome, None)

    @classmethod
    def not_found(
        cls, reason_code: ReplayTargetOutcomeReadReason
    ) -> ReplayTargetOutcomeReadResult:
        return cls(ReplayTargetOutcomeReadStatus.NOT_FOUND, None, reason_code)


@dataclass(frozen=True, slots=True)
class ReplayScoredPrediction:
    scoring_schema_version: str
    source_replay_artifact_payload_sha256: str
    source_replay_snapshot_result_sha256: str
    dataset_id: str
    dataset_version: str
    lottery_type: LotteryType
    target_draw_number: str
    target_draw_date: date
    strategy_id: str
    strategy_version: str | None
    source_history_status: str
    source_history_reason_code: str | None
    source_prediction_status: str | None
    source_prediction_reason_code: str | None
    scoring_status: ReplayScoringStatus
    scoring_reason_code: ReplayScoringReason | None
    predicted_main_numbers: tuple[int, ...] | None
    target_outcome_sha256: str | None
    main_number_hit_count: int | None
    special_number_hit: bool | None
    prize_tier_id: BigLottoPrizeTierId | None
    prize_official_label: str | None
    no_prize_result: NoPrizeResult | None
    scored_result_sha256: str

    def __post_init__(self) -> None:
        if self.scoring_schema_version != SCORING_SCHEMA_VERSION:
            raise ValueError("unsupported scoring_schema_version")
        _require_sha256(
            self.source_replay_artifact_payload_sha256,
            "source_replay_artifact_payload_sha256",
        )
        _require_sha256(
            self.source_replay_snapshot_result_sha256,
            "source_replay_snapshot_result_sha256",
        )
        _require_text(self.dataset_id, "dataset_id")
        _require_text(self.dataset_version, "dataset_version")
        if self.lottery_type is not LotteryType.BIG_LOTTO:
            raise ValueError("Replay prize scoring currently supports BIG_LOTTO only")
        validate_replay_target_draw_number(self.target_draw_number)
        if type(self.target_draw_date) is not date:
            raise ValueError("target_draw_date must be a date")
        _require_text(self.strategy_id, "strategy_id")
        if self.strategy_version is not None:
            _require_text(self.strategy_version, "strategy_version")
        _require_text(self.source_history_status, "source_history_status")

        history_ok = self.source_history_status == "OK"
        if history_ok:
            if self.source_history_reason_code is not None:
                raise ValueError("OK source history must not carry a reason")
            if self.source_prediction_status is None:
                raise ValueError("OK source history requires a prediction status")
        else:
            if self.source_history_reason_code is None:
                raise ValueError("closed source history requires a reason")
            if self.source_prediction_status is not None or self.source_prediction_reason_code:
                raise ValueError("closed source history cannot carry prediction fields")

        prediction_ok = self.source_prediction_status == "OK"
        if prediction_ok:
            if self.source_prediction_reason_code is not None:
                raise ValueError("OK source prediction must not carry a reason")
            if self.predicted_main_numbers is None:
                raise ValueError("OK source prediction requires predicted_main_numbers")
            _validate_main_numbers(self.predicted_main_numbers, "predicted_main_numbers")
            if self.strategy_version is None:
                raise ValueError("OK source prediction requires a complete strategy identity")
        elif self.source_prediction_status is not None:
            if self.source_prediction_reason_code is None:
                raise ValueError("closed source prediction requires a reason")
            if self.predicted_main_numbers is not None:
                raise ValueError("closed source prediction cannot carry predicted numbers")

        scoring_fields = (
            self.main_number_hit_count,
            self.special_number_hit,
            self.prize_tier_id,
            self.prize_official_label,
            self.no_prize_result,
        )
        if self.scoring_status is ReplayScoringStatus.SCORED:
            if self.scoring_reason_code is not None:
                raise ValueError("SCORED must not carry a scoring reason")
            if not prediction_ok or self.target_outcome_sha256 is None:
                raise ValueError("SCORED requires an OK prediction and target outcome")
            _require_sha256(self.target_outcome_sha256, "target_outcome_sha256")
            if type(self.main_number_hit_count) is not int:
                raise ValueError("SCORED requires main_number_hit_count")
            if not 0 <= self.main_number_hit_count <= BIG_LOTTO_RULE_CONTRACT.main_number_count:
                raise ValueError("main_number_hit_count is outside the Big Lotto range")
            if type(self.special_number_hit) is not bool:
                raise ValueError("SCORED requires special_number_hit")
            winning = self.prize_tier_id is not None or self.prize_official_label is not None
            losing = self.no_prize_result is not None
            if winning == losing:
                raise ValueError("SCORED requires exactly one winning tier or NO_PRIZE")
            if winning:
                if self.prize_tier_id is None or self.prize_official_label is None:
                    raise ValueError("winning result requires tier id and official label")
                _require_text(self.prize_official_label, "prize_official_label")
                tier = next(
                    candidate
                    for candidate in BIG_LOTTO_RULE_CONTRACT.prize_rule.tiers
                    if candidate.tier_id is self.prize_tier_id
                )
                if (
                    tier.official_label != self.prize_official_label
                    or tier.main_hits != self.main_number_hit_count
                    or tier.special_hit is not self.special_number_hit
                ):
                    raise ValueError("winning tier does not match the canonical hit signature")
            elif self.no_prize_result is not NoPrizeResult.NO_PRIZE:
                raise ValueError("losing result must be explicit NO_PRIZE")
        else:
            if any(value is not None for value in scoring_fields):
                raise ValueError("not-scored results cannot carry hit or prize fields")
            expected_reason = {
                ReplayScoringStatus.NOT_SCORED_HISTORY_CLOSED: (
                    ReplayScoringReason.SOURCE_HISTORY_CLOSED
                ),
                ReplayScoringStatus.NOT_SCORED_PREDICTION_CLOSED: (
                    ReplayScoringReason.SOURCE_PREDICTION_CLOSED
                ),
                ReplayScoringStatus.TARGET_IDENTITY_MISMATCH: (
                    ReplayScoringReason.TARGET_IDENTITY_MISMATCH
                ),
            }.get(self.scoring_status)
            if self.scoring_status is ReplayScoringStatus.TARGET_OUTCOME_NOT_FOUND:
                if self.scoring_reason_code not in {
                    ReplayScoringReason.TARGET_OUTCOME_NOT_FOUND,
                    ReplayScoringReason.TARGET_OUTCOME_STORAGE_UNAVAILABLE,
                }:
                    raise ValueError("TARGET_OUTCOME_NOT_FOUND requires a target read reason")
            elif self.scoring_reason_code is not expected_reason:
                raise ValueError("scoring status and reason_code do not agree")

            if self.scoring_status is ReplayScoringStatus.NOT_SCORED_HISTORY_CLOSED:
                if history_ok or self.target_outcome_sha256 is not None:
                    raise ValueError("history-closed result has incompatible fields")
            elif self.scoring_status is ReplayScoringStatus.NOT_SCORED_PREDICTION_CLOSED:
                if not history_ok or prediction_ok or self.target_outcome_sha256 is not None:
                    raise ValueError("prediction-closed result has incompatible fields")
            elif self.scoring_status is ReplayScoringStatus.TARGET_OUTCOME_NOT_FOUND:
                if not prediction_ok or self.target_outcome_sha256 is not None:
                    raise ValueError("missing-outcome result has incompatible fields")
            elif self.scoring_status is ReplayScoringStatus.TARGET_IDENTITY_MISMATCH:
                if not prediction_ok or self.target_outcome_sha256 is None:
                    raise ValueError("target-mismatch result requires the loaded outcome hash")
                _require_sha256(self.target_outcome_sha256, "target_outcome_sha256")

        _require_sha256(self.scored_result_sha256, "scored_result_sha256")
        if self.scored_result_sha256 != recompute_scored_result_sha256(self):
            raise ValueError("scored_result_sha256 does not match scored record content")

    @classmethod
    def create(cls, **values: Any) -> ReplayScoredPrediction:
        payload = replay_scored_prediction_canonical_dict(values, include_hash=False)
        return cls(**values, scored_result_sha256=_canonical_sha256(payload))


def replay_scored_prediction_canonical_dict(
    record_or_values: ReplayScoredPrediction | dict[str, Any],
    *,
    include_hash: bool = True,
) -> dict[str, Any]:
    if isinstance(record_or_values, ReplayScoredPrediction):
        values = {
            field.name: getattr(record_or_values, field.name)
            for field in fields(record_or_values)
        }
    else:
        values = record_or_values
    payload: dict[str, Any] = {
        "dataset_id": values["dataset_id"],
        "dataset_version": values["dataset_version"],
        "lottery_type": values["lottery_type"].value,
        "scoring_schema_version": values["scoring_schema_version"],
        "scoring_status": values["scoring_status"].value,
        "source_history_status": values["source_history_status"],
        "source_replay_artifact_payload_sha256": values[
            "source_replay_artifact_payload_sha256"
        ],
        "source_replay_snapshot_result_sha256": values[
            "source_replay_snapshot_result_sha256"
        ],
        "strategy_id": values["strategy_id"],
        "target_draw_date": values["target_draw_date"].isoformat(),
        "target_draw_number": values["target_draw_number"],
    }
    optional_scalars = (
        "source_history_reason_code",
        "source_prediction_status",
        "source_prediction_reason_code",
        "strategy_version",
        "target_outcome_sha256",
        "main_number_hit_count",
        "special_number_hit",
        "prize_official_label",
    )
    for key in optional_scalars:
        if values.get(key) is not None:
            payload[key] = values[key]
    for key in ("scoring_reason_code", "prize_tier_id", "no_prize_result"):
        if values.get(key) is not None:
            payload[key] = values[key].value
    if values.get("predicted_main_numbers") is not None:
        payload["predicted_main_numbers"] = list(values["predicted_main_numbers"])
    if include_hash:
        payload["scored_result_sha256"] = values["scored_result_sha256"]
    return payload


def recompute_scored_result_sha256(record: ReplayScoredPrediction) -> str:
    return _canonical_sha256(
        replay_scored_prediction_canonical_dict(record, include_hash=False)
    )


@dataclass(frozen=True, slots=True)
class ReplayScoringStrategyIdentity:
    strategy_id: str
    strategy_version: str | None

    def __post_init__(self) -> None:
        _require_text(self.strategy_id, "strategy_id")
        if self.strategy_version is not None:
            _require_text(self.strategy_version, "strategy_version")


_TIER_COUNT_FIELDS = {
    BigLottoPrizeTierId.FIRST: "first_prize_count",
    BigLottoPrizeTierId.SECOND: "second_prize_count",
    BigLottoPrizeTierId.THIRD: "third_prize_count",
    BigLottoPrizeTierId.FOURTH: "fourth_prize_count",
    BigLottoPrizeTierId.FIFTH: "fifth_prize_count",
    BigLottoPrizeTierId.SIXTH: "sixth_prize_count",
    BigLottoPrizeTierId.SEVENTH: "seventh_prize_count",
    BigLottoPrizeTierId.GENERAL: "general_prize_count",
}


@dataclass(frozen=True, slots=True)
class ReplayPrizeAggregation:
    aggregation_schema_version: str
    strategy_id: str | None
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
    aggregation_sha256: str

    def __post_init__(self) -> None:
        if self.aggregation_schema_version != AGGREGATION_SCHEMA_VERSION:
            raise ValueError("unsupported aggregation_schema_version")
        if self.strategy_id is None:
            if self.strategy_version is not None:
                raise ValueError("overall aggregation cannot carry strategy_version")
        else:
            _require_text(self.strategy_id, "strategy_id")
            if self.strategy_version is not None:
                _require_text(self.strategy_version, "strategy_version")
        count_names = (
            "source_snapshot_count",
            "scored_count",
            "history_closed_count",
            "prediction_closed_count",
            "target_outcome_not_found_count",
            "target_identity_mismatch_count",
            *_TIER_COUNT_FIELDS.values(),
            "no_prize_count",
        )
        for name in count_names:
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        closed_total = (
            self.history_closed_count
            + self.prediction_closed_count
            + self.target_outcome_not_found_count
            + self.target_identity_mismatch_count
        )
        if self.source_snapshot_count != self.scored_count + closed_total:
            raise ValueError("source snapshot count does not equal scored plus closed counts")
        prize_total = sum(getattr(self, name) for name in _TIER_COUNT_FIELDS.values())
        if self.scored_count != prize_total + self.no_prize_count:
            raise ValueError("scored count does not equal prize-tier plus no-prize counts")
        _require_sha256(self.aggregation_sha256, "aggregation_sha256")
        if self.aggregation_sha256 != recompute_aggregation_sha256(self):
            raise ValueError("aggregation_sha256 does not match aggregation content")

    @classmethod
    def from_records(
        cls,
        records: tuple[ReplayScoredPrediction, ...],
        *,
        strategy_id: str | None = None,
        strategy_version: str | None = None,
    ) -> ReplayPrizeAggregation:
        if strategy_id is not None and any(record.strategy_id != strategy_id for record in records):
            raise ValueError("strategy aggregation contains a different strategy_id")
        values: dict[str, Any] = {
            "aggregation_schema_version": AGGREGATION_SCHEMA_VERSION,
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "source_snapshot_count": len(records),
            "scored_count": sum(
                record.scoring_status is ReplayScoringStatus.SCORED for record in records
            ),
            "history_closed_count": sum(
                record.scoring_status is ReplayScoringStatus.NOT_SCORED_HISTORY_CLOSED
                for record in records
            ),
            "prediction_closed_count": sum(
                record.scoring_status is ReplayScoringStatus.NOT_SCORED_PREDICTION_CLOSED
                for record in records
            ),
            "target_outcome_not_found_count": sum(
                record.scoring_status is ReplayScoringStatus.TARGET_OUTCOME_NOT_FOUND
                for record in records
            ),
            "target_identity_mismatch_count": sum(
                record.scoring_status is ReplayScoringStatus.TARGET_IDENTITY_MISMATCH
                for record in records
            ),
            "no_prize_count": sum(
                record.no_prize_result is NoPrizeResult.NO_PRIZE for record in records
            ),
        }
        for tier, name in _TIER_COUNT_FIELDS.items():
            values[name] = sum(record.prize_tier_id is tier for record in records)
        return cls(**values, aggregation_sha256=_canonical_sha256(_aggregation_payload(values)))


def _aggregation_payload(values: dict[str, Any]) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in values.items()
        if key != "aggregation_sha256" and value is not None
    }
    return payload


def replay_prize_aggregation_canonical_dict(
    aggregation: ReplayPrizeAggregation, *, include_hash: bool = True
) -> dict[str, Any]:
    values = {field.name: getattr(aggregation, field.name) for field in fields(aggregation)}
    payload = _aggregation_payload(values)
    if include_hash:
        payload["aggregation_sha256"] = aggregation.aggregation_sha256
    return payload


def recompute_aggregation_sha256(aggregation: ReplayPrizeAggregation) -> str:
    return _canonical_sha256(
        replay_prize_aggregation_canonical_dict(aggregation, include_hash=False)
    )


__all__ = [
    "AGGREGATION_SCHEMA_VERSION",
    "SCORING_SCHEMA_VERSION",
    "TARGET_OUTCOME_SCHEMA_VERSION",
    "ReplayPrizeAggregation",
    "ReplayScoredPrediction",
    "ReplayScoringReason",
    "ReplayScoringStatus",
    "ReplayScoringStrategyIdentity",
    "ReplayTargetOutcome",
    "ReplayTargetOutcomeReadReason",
    "ReplayTargetOutcomeReadResult",
    "ReplayTargetOutcomeReadStatus",
    "recompute_aggregation_sha256",
    "recompute_scored_result_sha256",
    "recompute_target_outcome_sha256",
    "replay_prize_aggregation_canonical_dict",
    "replay_scored_prediction_canonical_dict",
    "validate_replay_target_draw_number",
]
