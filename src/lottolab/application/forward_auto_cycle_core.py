"""Lottery-agnostic orchestration for one forward auto-cycle.

The core deliberately knows nothing about ticket rules, prediction schemas,
outcome schemas, scoring rules, strategy registries, or target sources.  A
lottery adapter owns those concerns and exposes only the operations needed to
advance one target safely.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, cast


class ForwardAutoCycleAdapter[TargetT, StreamT, HistoryT, PredictionT, OutcomeT](Protocol):
    """Small port implemented once per lottery type.

    The values passed through the port are intentionally opaque to the core.
    In particular, the core never interprets a target, strategy stream,
    history snapshot, prediction, outcome, or score.
    """

    lottery_type: str

    def resolve_next_target(self) -> TargetT | None: ...

    def list_enabled_strategy_streams(self) -> Sequence[StreamT]: ...

    def build_history_snapshot(self, target: TargetT) -> HistoryT: ...

    def run_strategy(
        self,
        stream: StreamT,
        target: TargetT,
        history: HistoryT,
    ) -> PredictionT: ...

    def prediction_exists(self, target: TargetT, stream: StreamT) -> bool: ...

    def read_current_outcome(self, target: TargetT) -> OutcomeT | None: ...

    def resolve_official_outcome(self, target: TargetT) -> OutcomeT | None: ...

    def update_outcome(self, target: TargetT, outcome: OutcomeT) -> OutcomeT: ...

    def outcomes_equal(self, left: OutcomeT, right: OutcomeT) -> bool: ...

    def score_prediction(self, prediction: PredictionT, outcome: OutcomeT) -> object: ...

    def rescore_target(self, target: TargetT, outcome: OutcomeT) -> Sequence[object]: ...

    def refresh_reporting(self) -> object: ...


@dataclass(frozen=True, slots=True)
class ForwardAutoCycleStrategyFailure[StreamT]:
    """One strategy exception captured without stopping sibling streams."""

    stream: StreamT
    error_type: str
    error_message: str


@dataclass(frozen=True, slots=True)
class ForwardAutoCycleScoreFailure[PredictionT]:
    """One score exception captured without discarding other score attempts."""

    prediction: PredictionT
    error_type: str
    error_message: str


@dataclass(frozen=True, slots=True)
class ForwardAutoCycleResult[TargetT, StreamT, HistoryT, PredictionT, OutcomeT]:
    """Observable result of one core cycle."""

    lottery_type: str
    target: TargetT | None
    history: HistoryT | None
    existing_streams: tuple[StreamT, ...]
    created_predictions: tuple[PredictionT, ...]
    strategy_failures: tuple[ForwardAutoCycleStrategyFailure[StreamT], ...]
    score_results: tuple[object, ...]
    score_failures: tuple[ForwardAutoCycleScoreFailure[PredictionT], ...]
    rescore_results: tuple[object, ...]
    current_outcome: OutcomeT | None
    official_outcome: OutcomeT | None
    outcome_status: str
    warnings: tuple[str, ...]
    reporting: object | None
    next_action: str


class ForwardAutoCycleCore[TargetT, StreamT, HistoryT, PredictionT, OutcomeT]:
    """Run the shared resolve → predict → outcome → report flow."""

    def __init__(
        self,
        adapter: ForwardAutoCycleAdapter[
            TargetT, StreamT, HistoryT, PredictionT, OutcomeT
        ],
    ) -> None:
        self._adapter = adapter

    def run(self) -> ForwardAutoCycleResult[TargetT, StreamT, HistoryT, PredictionT, OutcomeT]:
        target = self._adapter.resolve_next_target()
        if target is None:
            return ForwardAutoCycleResult(
                lottery_type=self._adapter.lottery_type,
                target=None,
                history=None,
                existing_streams=(),
                created_predictions=(),
                strategy_failures=(),
                score_results=(),
                score_failures=(),
                rescore_results=(),
                current_outcome=None,
                official_outcome=None,
                outcome_status="NO_TARGET",
                warnings=(),
                reporting=None,
                next_action="NO_TARGET",
            )

        history = self._adapter.build_history_snapshot(target)
        warnings = self._history_warnings(history)
        existing_streams: list[StreamT] = []
        created_predictions: list[PredictionT] = []
        strategy_failures: list[ForwardAutoCycleStrategyFailure[StreamT]] = []

        for stream in self._adapter.list_enabled_strategy_streams():
            if self._adapter.prediction_exists(target, stream):
                existing_streams.append(stream)
                continue
            try:
                created_predictions.append(
                    self._adapter.run_strategy(stream, target, history)
                )
            except Exception as exc:
                strategy_failures.append(
                    ForwardAutoCycleStrategyFailure(
                        stream=stream,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )

        current_outcome = self._adapter.read_current_outcome(target)
        official_outcome = self._adapter.resolve_official_outcome(target)
        outcome = current_outcome
        outcome_status = "OUTCOME_PENDING"

        if official_outcome is not None:
            if current_outcome is None:
                outcome = self._adapter.update_outcome(target, official_outcome)
                outcome_status = "NEW_OUTCOME"
            elif self._adapter.outcomes_equal(current_outcome, official_outcome):
                outcome_status = "IDENTICAL_OUTCOME"
            elif self._should_update_outcome(target, current_outcome, official_outcome):
                outcome = self._adapter.update_outcome(target, official_outcome)
                outcome_status = "CORRECTED_OUTCOME"
            else:
                warnings = (*warnings, "OWNER_OUTCOME_PRESERVED")
                outcome_status = "OWNER_OUTCOME_PRESERVED"
        elif current_outcome is not None:
            outcome_status = "CURRENT_OUTCOME_PRESENT"

        score_results: list[object] = []
        score_failures: list[ForwardAutoCycleScoreFailure[PredictionT]] = []
        if outcome is not None:
            for prediction in created_predictions:
                try:
                    score_results.append(self._adapter.score_prediction(prediction, outcome))
                except Exception as exc:
                    score_failures.append(
                        ForwardAutoCycleScoreFailure(
                            prediction=prediction,
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    )

        rescore_results: tuple[object, ...] = ()
        if outcome is not None and (
            created_predictions
            or outcome_status in {"NEW_OUTCOME", "CORRECTED_OUTCOME"}
        ):
            rescore_results = tuple(self._adapter.rescore_target(target, outcome))

        reporting = self._adapter.refresh_reporting()
        return ForwardAutoCycleResult(
            lottery_type=self._adapter.lottery_type,
            target=target,
            history=history,
            existing_streams=tuple(existing_streams),
            created_predictions=tuple(created_predictions),
            strategy_failures=tuple(strategy_failures),
            score_results=tuple(score_results),
            score_failures=tuple(score_failures),
            rescore_results=rescore_results,
            current_outcome=outcome,
            official_outcome=official_outcome,
            outcome_status=outcome_status,
            warnings=tuple(warnings),
            reporting=reporting,
            next_action=self._next_action(
                created_predictions=created_predictions,
                outcome=outcome,
                outcome_status=outcome_status,
            ),
        )

    def _history_warnings(self, history: HistoryT) -> tuple[str, ...]:
        warning_reader = getattr(self._adapter, "history_warnings", None)
        if not callable(warning_reader):
            return ()
        typed_warning_reader = cast(Callable[[HistoryT], Sequence[object]], warning_reader)
        warnings = typed_warning_reader(history)
        return tuple(str(warning) for warning in warnings)

    def _should_update_outcome(
        self,
        target: TargetT,
        current: OutcomeT,
        official: OutcomeT,
    ) -> bool:
        decision = getattr(self._adapter, "should_update_outcome", None)
        if not callable(decision):
            return True
        return bool(decision(target, current, official))

    @staticmethod
    def _next_action(
        *,
        created_predictions: Sequence[PredictionT],
        outcome: OutcomeT | None,
        outcome_status: str,
    ) -> str:
        if created_predictions and outcome_status == "NEW_OUTCOME":
            return "PREDICTIONS_CREATED_AND_OUTCOME_RECORDED"
        if created_predictions and outcome_status == "CORRECTED_OUTCOME":
            return "PREDICTIONS_CREATED_AND_OUTCOME_CORRECTED"
        if created_predictions and outcome is not None:
            return "PREDICTIONS_CREATED_AND_SCORED"
        if created_predictions:
            return "PREDICTIONS_CREATED_WAITING_FOR_OUTCOME"
        if outcome_status == "NEW_OUTCOME":
            return "OUTCOME_RECORDED_AND_RESCORED"
        if outcome_status == "CORRECTED_OUTCOME":
            return "OUTCOME_CORRECTED_AND_RESCORED"
        if outcome_status == "IDENTICAL_OUTCOME":
            return "NO_OP"
        if outcome is not None:
            return "PREDICTIONS_ALREADY_CURRENT"
        return "WAITING_FOR_OUTCOME"


__all__ = [
    "ForwardAutoCycleAdapter",
    "ForwardAutoCycleCore",
    "ForwardAutoCycleResult",
    "ForwardAutoCycleScoreFailure",
    "ForwardAutoCycleStrategyFailure",
]
