"""Replay use case: build one closed-result causal Big Lotto history window."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lottolab.application.ports import DrawHistoryReaderFactory, TargetDrawNotFoundError
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_history import ReplayCausalDrawRow


class BuildCausalHistoryStatus(StrEnum):
    OK = "OK"
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    INVALID_BOUNDS = "INVALID_BOUNDS"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"


class BuildCausalHistoryReason(StrEnum):
    TARGET_DRAW_NOT_FOUND = "TARGET_DRAW_NOT_FOUND"
    MAXIMUM_HISTORY_DRAWS_NOT_POSITIVE = "MAXIMUM_HISTORY_DRAWS_NOT_POSITIVE"
    MINIMUM_HISTORY_DRAWS_NOT_POSITIVE = "MINIMUM_HISTORY_DRAWS_NOT_POSITIVE"
    MINIMUM_EXCEEDS_MAXIMUM = "MINIMUM_EXCEEDS_MAXIMUM"
    AVAILABLE_HISTORY_BELOW_MINIMUM = "AVAILABLE_HISTORY_BELOW_MINIMUM"


@dataclass(frozen=True, slots=True)
class BuildCausalHistoryInput:
    lottery_type: LotteryType
    target_draw_number: str
    maximum_history_draws: int | None = None
    minimum_history_draws: int | None = None


@dataclass(frozen=True, slots=True)
class BuildCausalHistoryResult:
    """A closed result binding ``status`` to which fields are populated.

    ``history`` and ``available_history_count`` are populated only for OK
    results; ``reason_code`` is populated only for non-OK results.
    """

    status: BuildCausalHistoryStatus
    lottery_type: LotteryType
    target_draw_number: str
    applied_maximum_history_draws: int | None
    history: tuple[ReplayCausalDrawRow, ...] | None
    available_history_count: int | None
    reason_code: BuildCausalHistoryReason | None

    def __post_init__(self) -> None:
        if self.status is BuildCausalHistoryStatus.OK:
            if (
                self.history is None
                or self.available_history_count is None
                or self.reason_code is not None
            ):
                raise ValueError(
                    "OK results require history and available_history_count and no reason code"
                )
        elif (
            self.history is not None
            or self.available_history_count is not None
            or self.reason_code is None
        ):
            raise ValueError(
                "non-OK results require a reason code and no history or available_history_count"
            )


class BuildCausalHistory:
    """Validate bounds, then resolve one causal Big Lotto history window."""

    def __init__(self, reader_factory: DrawHistoryReaderFactory) -> None:
        self._reader_factory = reader_factory

    def execute(self, request: BuildCausalHistoryInput) -> BuildCausalHistoryResult:
        bounds_failure = self._validate_bounds(request)
        if bounds_failure is not None:
            return bounds_failure

        reader = self._reader_factory()
        try:
            history = reader.read_causal_history(
                request.lottery_type,
                request.target_draw_number,
                maximum_history_draws=request.maximum_history_draws,
            )
        except TargetDrawNotFoundError:
            return self._failure(
                request,
                BuildCausalHistoryStatus.TARGET_NOT_FOUND,
                BuildCausalHistoryReason.TARGET_DRAW_NOT_FOUND,
            )

        available_history_count = len(history)
        if (
            request.minimum_history_draws is not None
            and available_history_count < request.minimum_history_draws
        ):
            return self._failure(
                request,
                BuildCausalHistoryStatus.INSUFFICIENT_HISTORY,
                BuildCausalHistoryReason.AVAILABLE_HISTORY_BELOW_MINIMUM,
            )

        return BuildCausalHistoryResult(
            status=BuildCausalHistoryStatus.OK,
            lottery_type=request.lottery_type,
            target_draw_number=request.target_draw_number,
            applied_maximum_history_draws=request.maximum_history_draws,
            history=history,
            available_history_count=available_history_count,
            reason_code=None,
        )

    @staticmethod
    def _validate_bounds(
        request: BuildCausalHistoryInput,
    ) -> BuildCausalHistoryResult | None:
        if (
            request.maximum_history_draws is not None
            and request.maximum_history_draws <= 0
        ):
            return BuildCausalHistory._failure(
                request,
                BuildCausalHistoryStatus.INVALID_BOUNDS,
                BuildCausalHistoryReason.MAXIMUM_HISTORY_DRAWS_NOT_POSITIVE,
            )
        if (
            request.minimum_history_draws is not None
            and request.minimum_history_draws <= 0
        ):
            return BuildCausalHistory._failure(
                request,
                BuildCausalHistoryStatus.INVALID_BOUNDS,
                BuildCausalHistoryReason.MINIMUM_HISTORY_DRAWS_NOT_POSITIVE,
            )
        if (
            request.maximum_history_draws is not None
            and request.minimum_history_draws is not None
            and request.minimum_history_draws > request.maximum_history_draws
        ):
            return BuildCausalHistory._failure(
                request,
                BuildCausalHistoryStatus.INVALID_BOUNDS,
                BuildCausalHistoryReason.MINIMUM_EXCEEDS_MAXIMUM,
            )
        return None

    @staticmethod
    def _failure(
        request: BuildCausalHistoryInput,
        status: BuildCausalHistoryStatus,
        reason: BuildCausalHistoryReason,
    ) -> BuildCausalHistoryResult:
        return BuildCausalHistoryResult(
            status=status,
            lottery_type=request.lottery_type,
            target_draw_number=request.target_draw_number,
            applied_maximum_history_draws=request.maximum_history_draws,
            history=None,
            available_history_count=None,
            reason_code=reason,
        )


__all__ = [
    "BuildCausalHistory",
    "BuildCausalHistoryInput",
    "BuildCausalHistoryReason",
    "BuildCausalHistoryResult",
    "BuildCausalHistoryStatus",
]
