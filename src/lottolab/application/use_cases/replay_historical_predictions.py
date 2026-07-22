"""Execute Replay predictions for a fixed set of target draws x strategies.

Composes two existing, unmodified use cases — never a second prediction
engine: :class:`BuildCausalHistory` resolves one causal history window per
target, and :class:`GenerateOneBet` resolves one prediction per
target x strategy pair, delegating to whichever adapter the caller injected.
This module only orchestrates and records; it contains no prediction logic
of its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from lottolab.application.use_cases.build_causal_history import (
    BuildCausalHistory,
    BuildCausalHistoryInput,
    BuildCausalHistoryResult,
    BuildCausalHistoryStatus,
)
from lottolab.application.use_cases.generate_bet import GenerateOneBet, GenerateOneBetInput
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_history import ReplayCausalDrawRow
from lottolab.domain.replay_predictions import ReplayPredictionSnapshot, ReplayTarget
from lottolab.evidence.replay_artifact import build_replay_prediction_snapshot
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.catalog import StrategyCatalog, UnknownStrategyError


class DuplicateReplayTargetError(ValueError):
    """``targets`` contains two entries with the same ``draw_number``."""


class DuplicateReplayStrategyError(ValueError):
    """``strategy_ids`` contains the same strategy id twice."""


@dataclass(frozen=True, slots=True)
class ReplayHistoricalPredictionsInput:
    lottery_type: LotteryType
    dataset_id: str
    dataset_version: str
    targets: tuple[ReplayTarget, ...]
    strategy_ids: tuple[str, ...]
    maximum_history_draws: int | None = None
    minimum_history_draws: int | None = None

    def __post_init__(self) -> None:
        if not self.targets:
            raise ValueError("targets must not be empty")
        if not self.strategy_ids:
            raise ValueError("strategy_ids must not be empty")
        draw_numbers = [target.draw_number for target in self.targets]
        if len(set(draw_numbers)) != len(draw_numbers):
            raise DuplicateReplayTargetError("targets must not contain duplicate draw numbers")
        if len(set(self.strategy_ids)) != len(self.strategy_ids):
            raise DuplicateReplayStrategyError("strategy_ids must not contain duplicates")


@dataclass(frozen=True, slots=True)
class ReplayHistoricalPredictionsResult:
    """``snapshots`` is ordered target-major, strategy-minor, mirroring the
    caller-supplied ``targets``/``strategy_ids`` order exactly — Replay never
    silently reorders a caller's pairs, matching ``BuildCausalHistory``'s own
    never-reorder convention."""

    snapshots: tuple[ReplayPredictionSnapshot, ...]


def _to_causal_draw_rows(history: tuple[ReplayCausalDrawRow, ...]) -> tuple[CausalDrawRow, ...]:
    """Narrow Replay provenance rows down to the strategy adapter's own input shape.

    Deliberately drops ``special_number``: the strategy-facing ``CausalDrawRow``
    has no such field and must never be widened to add one (see
    ``lottolab.domain.replay_history`` module docstring). Replay's own
    provenance hash is computed separately, from the full
    ``ReplayCausalDrawRow`` tuple, so no information is actually lost.
    """

    return tuple(
        CausalDrawRow(
            draw=row.draw_number,
            date=row.draw_date.isoformat(),
            numbers=row.main_numbers,
        )
        for row in history
    )


class ReplayHistoricalPredictions:
    """Resolve one closed-result :class:`ReplayPredictionSnapshot` per target x strategy pair."""

    def __init__(
        self,
        build_causal_history: BuildCausalHistory,
        generate_one_bet: GenerateOneBet,
        catalog: StrategyCatalog,
    ) -> None:
        self._build_causal_history = build_causal_history
        self._generate_one_bet = generate_one_bet
        self._catalog = catalog

    def execute(
        self, request: ReplayHistoricalPredictionsInput
    ) -> ReplayHistoricalPredictionsResult:
        history_by_target: dict[str, BuildCausalHistoryResult] = {}
        snapshots: list[ReplayPredictionSnapshot] = []

        for target in request.targets:
            history_result = history_by_target.get(target.draw_number)
            if history_result is None:
                history_result = self._build_causal_history.execute(
                    BuildCausalHistoryInput(
                        lottery_type=request.lottery_type,
                        target_draw_number=target.draw_number,
                        maximum_history_draws=request.maximum_history_draws,
                        minimum_history_draws=request.minimum_history_draws,
                    )
                )
                history_by_target[target.draw_number] = history_result

            for strategy_id in request.strategy_ids:
                snapshots.append(
                    self._build_one_snapshot(request, target, strategy_id, history_result)
                )

        return ReplayHistoricalPredictionsResult(snapshots=tuple(snapshots))

    def _build_one_snapshot(
        self,
        request: ReplayHistoricalPredictionsInput,
        target: ReplayTarget,
        strategy_id: str,
        history_result: BuildCausalHistoryResult,
    ) -> ReplayPredictionSnapshot:
        try:
            descriptor = self._catalog.get(strategy_id)
        except UnknownStrategyError:
            strategy_identity = None
        else:
            strategy_identity = (
                descriptor.strategy_id,
                descriptor.strategy_name,
                descriptor.version,
            )

        if history_result.status is not BuildCausalHistoryStatus.OK:
            return build_replay_prediction_snapshot(
                dataset_id=request.dataset_id,
                dataset_version=request.dataset_version,
                lottery_type=request.lottery_type,
                target=target,
                strategy_id=strategy_id,
                strategy_identity=strategy_identity,
                history_status=history_result.status.value,
                history_reason_code=(
                    history_result.reason_code.value
                    if history_result.reason_code is not None
                    else None
                ),
                causal_history=None,
                prediction_status=None,
                prediction_reason_code=None,
                predicted_main_numbers=None,
            )

        assert history_result.history is not None  # OK results always carry history
        prediction_result = self._generate_one_bet.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=request.lottery_type,
                history=_to_causal_draw_rows(history_result.history),
            )
        )
        return build_replay_prediction_snapshot(
            dataset_id=request.dataset_id,
            dataset_version=request.dataset_version,
            lottery_type=request.lottery_type,
            target=target,
            strategy_id=strategy_id,
            strategy_identity=strategy_identity,
            history_status=history_result.status.value,
            history_reason_code=None,
            causal_history=history_result.history,
            prediction_status=prediction_result.status.value,
            prediction_reason_code=(
                prediction_result.reason_code.value
                if prediction_result.reason_code is not None
                else None
            ),
            predicted_main_numbers=prediction_result.numbers,
        )


__all__ = [
    "DuplicateReplayStrategyError",
    "DuplicateReplayTargetError",
    "ReplayHistoricalPredictions",
    "ReplayHistoricalPredictionsInput",
    "ReplayHistoricalPredictionsResult",
]
