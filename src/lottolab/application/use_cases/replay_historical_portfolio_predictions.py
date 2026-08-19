"""Execute Replay PORTFOLIO predictions for a fixed set of target draws x strategies.

The ``ResponseShape.PORTFOLIO`` analog of
:mod:`lottolab.application.use_cases.replay_historical_predictions`. Composes
two existing, unmodified use cases -- never a second prediction engine:
:class:`~lottolab.application.use_cases.build_causal_history.BuildCausalHistory`
resolves one causal history window per target (the identical causal-history
boundary the SINGLE_TICKET path uses), and
:class:`~lottolab.application.use_cases.generate_bet.GeneratePortfolio`
resolves each uncached target x strategy pair, delegating to whichever
PORTFOLIO adapter the caller injected. This module only orchestrates; it
contains no prediction logic and computes no score.

Deliberately carries no research cache: a single-ticket
:class:`~lottolab.application.use_cases.replay_historical_predictions.ReplayResearchCache`
entry stores one ``predicted_main_numbers`` tuple, and reusing that same
cache/key shape for a multi-ticket ``predicted_tickets`` payload would either
silently narrow a portfolio down to its cache-key shape or require widening
the single-ticket cache contract -- both out of scope here. Every call
recomputes; add a portfolio-shaped cache later if profiling shows it is
needed.
"""

from __future__ import annotations

from dataclasses import dataclass

from lottolab.application.use_cases.build_causal_history import (
    BuildCausalHistory,
    BuildCausalHistoryInput,
    BuildCausalHistoryResult,
    BuildCausalHistoryStatus,
)
from lottolab.application.use_cases.generate_bet import GenerateOneBetInput, GeneratePortfolio
from lottolab.application.use_cases.replay_historical_predictions import to_causal_draw_rows
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_history import ReplayCausalDrawRow
from lottolab.domain.replay_predictions import (
    PORTFOLIO_SNAPSHOT_SCHEMA_VERSION,
    ReplayPortfolioPredictionSnapshot,
    ReplaySourceMode,
    ReplayTarget,
)
from lottolab.evidence.replay_artifact import causal_history_sha256
from lottolab.strategies.adapters.base import CausalDrawRow
from lottolab.strategies.catalog import StrategyCatalog, UnknownStrategyError


class DuplicateReplayPortfolioTargetError(ValueError):
    """``targets`` contains two entries with the same ``draw_number``."""


class DuplicateReplayPortfolioStrategyError(ValueError):
    """``strategy_ids`` contains the same strategy id twice."""


@dataclass(frozen=True, slots=True)
class ReplayHistoricalPortfolioPredictionsInput:
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
            raise DuplicateReplayPortfolioTargetError(
                "targets must not contain duplicate draw numbers"
            )
        if len(set(self.strategy_ids)) != len(self.strategy_ids):
            raise DuplicateReplayPortfolioStrategyError("strategy_ids must not contain duplicates")


@dataclass(frozen=True, slots=True)
class ReplayHistoricalPortfolioPredictionsResult:
    """``snapshots`` is ordered target-major, strategy-minor, mirroring the
    caller-supplied ``targets``/``strategy_ids`` order exactly -- the same
    never-reorder convention
    :class:`~lottolab.application.use_cases.replay_historical_predictions.ReplayHistoricalPredictionsResult`
    already guarantees for the SINGLE_TICKET path."""

    snapshots: tuple[ReplayPortfolioPredictionSnapshot, ...]


def _assemble_snapshot(
    *,
    dataset_id: str,
    dataset_version: str,
    lottery_type: LotteryType,
    target: ReplayTarget,
    strategy_id: str,
    strategy_identity: tuple[str, str, str] | None,
    history_status: str,
    history_reason_code: str | None,
    causal_history: tuple[ReplayCausalDrawRow, ...] | None,
    prediction_status: str | None,
    prediction_reason_code: str | None,
    predicted_tickets: tuple[tuple[int, ...], ...] | None,
) -> ReplayPortfolioPredictionSnapshot:
    """Assemble one immutable :class:`ReplayPortfolioPredictionSnapshot`.

    Mirrors
    :func:`~lottolab.evidence.replay_artifact.build_replay_prediction_snapshot`'s
    field derivation exactly (cutoff from the last causal-history row,
    ``strategy_identity`` unpacked the same way), minus its content-hash
    stamping -- see the domain type's own docstring for why this snapshot
    carries no ``result_sha256``.
    """

    adapter_id, adapter_name, adapter_version = (
        strategy_identity if strategy_identity is not None else (None, None, None)
    )
    causal_history_count = len(causal_history) if causal_history is not None else None
    causal_history_hash = (
        causal_history_sha256(causal_history) if causal_history is not None else None
    )
    if causal_history:
        cutoff_draw_number: str | None = causal_history[-1].draw_number
        cutoff_draw_date = causal_history[-1].draw_date
    else:
        cutoff_draw_number = None
        cutoff_draw_date = None

    return ReplayPortfolioPredictionSnapshot(
        snapshot_schema_version=PORTFOLIO_SNAPSHOT_SCHEMA_VERSION,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        lottery_type=lottery_type,
        source_mode=ReplaySourceMode.TARGET_NATIVE,
        target_draw_number=target.draw_number,
        target_draw_date=target.draw_date,
        cutoff_draw_number=cutoff_draw_number,
        cutoff_draw_date=cutoff_draw_date,
        strategy_id=strategy_id,
        strategy_version=adapter_version,
        adapter_strategy_id=adapter_id,
        adapter_strategy_name=adapter_name,
        adapter_strategy_version=adapter_version,
        history_status=history_status,
        history_reason_code=history_reason_code,
        causal_history_count=causal_history_count,
        causal_history_sha256=causal_history_hash,
        prediction_status=prediction_status,
        prediction_reason_code=prediction_reason_code,
        predicted_tickets=predicted_tickets,
    )


class ReplayHistoricalPortfolioPredictions:
    """Resolve one closed-result :class:`ReplayPortfolioPredictionSnapshot` per
    target x strategy pair."""

    def __init__(
        self,
        build_causal_history: BuildCausalHistory,
        generate_portfolio: GeneratePortfolio,
        catalog: StrategyCatalog,
    ) -> None:
        self._build_causal_history = build_causal_history
        self._generate_portfolio = generate_portfolio
        self._catalog = catalog

    def execute(
        self, request: ReplayHistoricalPortfolioPredictionsInput
    ) -> ReplayHistoricalPortfolioPredictionsResult:
        history_by_target: dict[str, BuildCausalHistoryResult] = {}
        snapshots: list[ReplayPortfolioPredictionSnapshot] = []

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

            if history_result.status is BuildCausalHistoryStatus.OK:
                assert history_result.history is not None
                adapter_history = to_causal_draw_rows(history_result.history)
            else:
                adapter_history = None

            for strategy_id in request.strategy_ids:
                snapshots.append(
                    self._build_one_snapshot(
                        request,
                        target,
                        strategy_id,
                        history_result,
                        adapter_history=adapter_history,
                    )
                )

        return ReplayHistoricalPortfolioPredictionsResult(snapshots=tuple(snapshots))

    def _build_one_snapshot(
        self,
        request: ReplayHistoricalPortfolioPredictionsInput,
        target: ReplayTarget,
        strategy_id: str,
        history_result: BuildCausalHistoryResult,
        *,
        adapter_history: tuple[CausalDrawRow, ...] | None,
    ) -> ReplayPortfolioPredictionSnapshot:
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
            return _assemble_snapshot(
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
                predicted_tickets=None,
            )

        assert history_result.history is not None  # OK results always carry history
        assert adapter_history is not None

        prediction_result = self._generate_portfolio.execute(
            GenerateOneBetInput(
                strategy_id=strategy_id,
                lottery_type=request.lottery_type,
                history=adapter_history,
            )
        )
        return _assemble_snapshot(
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
            predicted_tickets=prediction_result.numbers,
        )


__all__ = [
    "DuplicateReplayPortfolioStrategyError",
    "DuplicateReplayPortfolioTargetError",
    "ReplayHistoricalPortfolioPredictions",
    "ReplayHistoricalPortfolioPredictionsInput",
    "ReplayHistoricalPortfolioPredictionsResult",
]
