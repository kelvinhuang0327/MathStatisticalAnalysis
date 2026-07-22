"""Replay execution domain types: one target identity, one immutable snapshot.

Pure dataclasses only — no hashing, no canonical-JSON logic. Snapshot content
hashing lives in :mod:`lottolab.evidence.replay_artifact` (the evidence layer
may depend on domain; domain must never depend on evidence). Status/reason
fields are plain strings echoing the originating use case's own closed-result
enums (``BuildCausalHistoryStatus``/``GenerateOneBetStatus`` and their reason
enums) so this module never imports the application layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from lottolab.domain.draws import LotteryType

SNAPSHOT_SCHEMA_VERSION = "1.0.0"


class ReplaySourceMode(StrEnum):
    """Closed for this task: history and prediction both resolve against the
    target's own lottery type — never a cross-lottery or hypothetical replay."""

    TARGET_NATIVE = "TARGET_NATIVE"


@dataclass(frozen=True, slots=True)
class ReplayTarget:
    """Identity of one draw Replay will attempt to predict — no outcome fields."""

    draw_number: str
    draw_date: date

    def __post_init__(self) -> None:
        if type(self.draw_number) is not str or not self.draw_number:
            raise ValueError("draw_number must be a non-empty string")
        if type(self.draw_date) is not date:
            raise ValueError("draw_date must be a date")


@dataclass(frozen=True, slots=True)
class ReplayPredictionSnapshot:
    """One immutable, closed-schema Replay outcome for one target x strategy pair.

    ``history_status`` is always populated. ``prediction_status`` is
    populated if and only if ``history_status == "OK"`` — GenerateOneBet is
    never invoked when the causal-history boundary itself failed closed.
    ``strategy_version``/``adapter_strategy_*`` are populated only when the
    injected catalog resolves ``strategy_id`` to a descriptor; an unresolved
    strategy id is an identity mismatch the use case must record, not raise.
    """

    snapshot_schema_version: str
    dataset_id: str
    dataset_version: str
    lottery_type: LotteryType
    source_mode: ReplaySourceMode
    target_draw_number: str
    target_draw_date: date
    cutoff_draw_number: str | None
    cutoff_draw_date: date | None
    strategy_id: str
    strategy_version: str | None
    adapter_strategy_id: str | None
    adapter_strategy_name: str | None
    adapter_strategy_version: str | None
    history_status: str
    history_reason_code: str | None
    causal_history_count: int | None
    causal_history_sha256: str | None
    prediction_status: str | None
    prediction_reason_code: str | None
    predicted_main_numbers: tuple[int, ...] | None
    result_sha256: str

    def __post_init__(self) -> None:
        if type(self.lottery_type) is not LotteryType:
            raise ValueError("lottery_type must be a LotteryType")
        if type(self.source_mode) is not ReplaySourceMode:
            raise ValueError("source_mode must be a ReplaySourceMode")
        if not self.strategy_id:
            raise ValueError("strategy_id must be a non-empty string")

        if (self.cutoff_draw_number is None) != (self.cutoff_draw_date is None):
            raise ValueError(
                "cutoff_draw_number and cutoff_draw_date must be both present or both absent"
            )

        history_ok = self.history_status == "OK"
        if history_ok:
            if self.history_reason_code is not None:
                raise ValueError("OK history_status must not carry a history_reason_code")
            if self.causal_history_count is None or self.causal_history_sha256 is None:
                raise ValueError("OK history_status requires causal_history_count and _sha256")
            if self.causal_history_count < 0:
                raise ValueError("causal_history_count must not be negative")
            if self.causal_history_count == 0:
                if self.cutoff_draw_number is not None or self.cutoff_draw_date is not None:
                    raise ValueError(
                        "OK history_status with zero causal history must not carry a cutoff"
                    )
            elif self.cutoff_draw_number is None or self.cutoff_draw_date is None:
                raise ValueError(
                    "OK history_status with non-zero causal history requires a cutoff"
                )
        else:
            if self.history_reason_code is None:
                raise ValueError("non-OK history_status requires a history_reason_code")
            if self.causal_history_count is not None or self.causal_history_sha256 is not None:
                raise ValueError(
                    "non-OK history_status must not carry causal_history_count or _sha256"
                )
            if self.cutoff_draw_number is not None or self.cutoff_draw_date is not None:
                raise ValueError("non-OK history_status must not carry a cutoff")
            if self.prediction_status is not None or self.prediction_reason_code is not None:
                raise ValueError("prediction is unattempted when history_status is not OK")
            if self.predicted_main_numbers is not None:
                raise ValueError("predicted_main_numbers requires an OK prediction_status")

        if self.cutoff_draw_number is not None and self.cutoff_draw_date is not None:
            cutoff_key = (self.cutoff_draw_date, int(self.cutoff_draw_number))
            target_key = (self.target_draw_date, int(self.target_draw_number))
            if cutoff_key >= target_key:
                raise ValueError("cutoff must represent a draw strictly before the target")

        if history_ok and self.prediction_status is None:
            raise ValueError("OK history_status requires an attempted prediction_status")

        prediction_ok = self.prediction_status == "OK"
        if prediction_ok:
            if self.prediction_reason_code is not None:
                raise ValueError("OK prediction_status must not carry a prediction_reason_code")
            if self.predicted_main_numbers is None:
                raise ValueError("OK prediction_status requires predicted_main_numbers")
        elif self.prediction_status is not None:
            if self.prediction_reason_code is None:
                raise ValueError("non-OK prediction_status requires a prediction_reason_code")
            if self.predicted_main_numbers is not None:
                raise ValueError("predicted_main_numbers requires an OK prediction_status")

        identity_present = (
            self.strategy_version,
            self.adapter_strategy_id,
            self.adapter_strategy_name,
            self.adapter_strategy_version,
        )
        if any(field is None for field in identity_present) and any(
            field is not None for field in identity_present
        ):
            raise ValueError("strategy/adapter identity fields must be all-present or all-absent")


__all__ = [
    "SNAPSHOT_SCHEMA_VERSION",
    "ReplayPredictionSnapshot",
    "ReplaySourceMode",
    "ReplayTarget",
]
