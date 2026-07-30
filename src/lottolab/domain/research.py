"""Stable vocabulary for LottoLab research-store records."""

from __future__ import annotations

from enum import StrEnum


class ResearchRunKind(StrEnum):
    LIVE_PREDICTION = "LIVE_PREDICTION"
    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"
    HISTORICAL_BACKTEST = "HISTORICAL_BACKTEST"
    REGENERATION = "REGENERATION"
    IMPORTED_LEGACY_REPORT = "IMPORTED_LEGACY_REPORT"
    REFERENCE_BASELINE = "REFERENCE_BASELINE"


class ResearchRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ResearchExecutionStatus(StrEnum):
    OK = "OK"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    STRATEGY_UNAVAILABLE = "STRATEGY_UNAVAILABLE"
    REJECTED = "REJECTED"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    CANCELLED = "CANCELLED"
    WAITING_FOR_DRAW = "WAITING_FOR_DRAW"


class StrategyProvenanceAvailability(StrEnum):
    """Whether a strategy snapshot has native source/runtime provenance."""

    COMPLETE = "COMPLETE"
    LEGACY_UNAVAILABLE = "LEGACY_UNAVAILABLE"


__all__ = [
    "ResearchExecutionStatus",
    "ResearchRunKind",
    "ResearchRunStatus",
    "StrategyProvenanceAvailability",
]
