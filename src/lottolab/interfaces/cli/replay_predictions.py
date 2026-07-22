"""Read-only BIG_LOTTO Replay predictions CLI composition."""

from __future__ import annotations

from typing import Annotated, NoReturn

import typer

from lottolab.application.draw_data import DrawDataApplicationError
from lottolab.application.use_cases.build_causal_history import BuildCausalHistory
from lottolab.application.use_cases.generate_bet import (
    GenerateOneBetStatus,
    build_production_generate_one_bet,
)
from lottolab.application.use_cases.replay_historical_predictions import (
    ReplayHistoricalPredictions,
    ReplayHistoricalPredictionsInput,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.replay_predictions import ReplayTarget
from lottolab.evidence.replay_artifact import build_replay_artifact, serialize_replay_artifact
from lottolab.infrastructure.persistence.draw_schema import (
    LocalDataError,
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.replay_history_reader import SQLiteDrawHistoryReader
from lottolab.infrastructure.persistence.repositories import SQLiteDrawDataRepository
from lottolab.strategies.catalog import StrategyCatalog, UnknownStrategyError, production_catalog


class ReplayPredictionsCliError(RuntimeError):
    """A caller-safe Replay CLI failure."""


def build_replay_predictions_cli_artifact(
    *,
    dataset_id: str,
    dataset_version: str,
    target_draws: tuple[str, ...],
    strategy_ids: tuple[str, ...],
    maximum_history_draws: int | None = None,
    minimum_history_draws: int | None = None,
) -> bytes:
    """Compose existing Replay contracts and return their canonical artifact bytes."""

    _validate_inputs(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        target_draws=target_draws,
        strategy_ids=strategy_ids,
        maximum_history_draws=maximum_history_draws,
        minimum_history_draws=minimum_history_draws,
    )
    catalog = production_catalog()
    _validate_strategies(catalog, strategy_ids)

    try:
        paths = resolve_local_data_paths()
    except LocalDataError as exc:
        raise ReplayPredictionsCliError("local draw database is unavailable") from exc
    if not paths.database.is_file():
        raise ReplayPredictionsCliError("local draw database is unavailable")

    repository = SQLiteDrawDataRepository(paths)
    targets: list[ReplayTarget] = []
    try:
        for draw_number in target_draws:
            record = repository.get_draw(LotteryType.BIG_LOTTO, draw_number)
            if record is None:
                raise ReplayPredictionsCliError(f"target draw was not found: {draw_number}")
            targets.append(
                ReplayTarget(draw_number=record.draw_number, draw_date=record.draw_date)
            )
    except DrawDataApplicationError as exc:
        raise ReplayPredictionsCliError("local draw database is unavailable") from exc

    target_tuple = tuple(targets)
    replay = ReplayHistoricalPredictions(
        BuildCausalHistory(lambda: SQLiteDrawHistoryReader(paths)),
        build_production_generate_one_bet(),
        catalog,
    )
    result = replay.execute(
        ReplayHistoricalPredictionsInput(
            lottery_type=LotteryType.BIG_LOTTO,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            targets=target_tuple,
            strategy_ids=strategy_ids,
            maximum_history_draws=maximum_history_draws,
            minimum_history_draws=minimum_history_draws,
        )
    )
    if any(
        snapshot.prediction_status == GenerateOneBetStatus.STRATEGY_UNAVAILABLE.value
        for snapshot in result.snapshots
    ):
        raise ReplayPredictionsCliError("a requested strategy is unavailable")

    artifact = build_replay_artifact(
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        lottery_type=LotteryType.BIG_LOTTO,
        strategy_ids=strategy_ids,
        targets=target_tuple,
        snapshots=result.snapshots,
    )
    return serialize_replay_artifact(artifact)


def replay_predictions_command(
    dataset_id: Annotated[str, typer.Option("--dataset-id")],
    dataset_version: Annotated[str, typer.Option("--dataset-version")],
    target_draw: Annotated[list[str], typer.Option("--target-draw")],
    strategy_id: Annotated[list[str], typer.Option("--strategy-id")],
    maximum_history_draws: Annotated[
        int | None,
        typer.Option("--maximum-history-draws", min=1),
    ] = None,
    minimum_history_draws: Annotated[
        int | None,
        typer.Option("--minimum-history-draws", min=1),
    ] = None,
) -> None:
    """Create a canonical Replay artifact from the existing local BIG_LOTTO database."""

    try:
        artifact_bytes = build_replay_predictions_cli_artifact(
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            target_draws=tuple(target_draw),
            strategy_ids=tuple(strategy_id),
            maximum_history_draws=maximum_history_draws,
            minimum_history_draws=minimum_history_draws,
        )
    except ReplayPredictionsCliError as exc:
        _fail(str(exc))
    except Exception:
        _fail("request failed safely")
    typer.echo(artifact_bytes.decode("utf-8"))


def _validate_inputs(
    *,
    dataset_id: str,
    dataset_version: str,
    target_draws: tuple[str, ...],
    strategy_ids: tuple[str, ...],
    maximum_history_draws: int | None,
    minimum_history_draws: int | None,
) -> None:
    if not dataset_id.strip():
        raise ReplayPredictionsCliError("dataset ID must not be blank")
    if not dataset_version.strip():
        raise ReplayPredictionsCliError("dataset version must not be blank")
    if not target_draws:
        raise ReplayPredictionsCliError("at least one target draw is required")
    if any(not draw_number.strip() for draw_number in target_draws):
        raise ReplayPredictionsCliError("target draws must not be blank")
    if len(set(target_draws)) != len(target_draws):
        raise ReplayPredictionsCliError("target draws must not contain duplicates")
    if not strategy_ids:
        raise ReplayPredictionsCliError("at least one strategy ID is required")
    if any(not strategy_id.strip() for strategy_id in strategy_ids):
        raise ReplayPredictionsCliError("strategy IDs must not be blank")
    if len(set(strategy_ids)) != len(strategy_ids):
        raise ReplayPredictionsCliError("strategy IDs must not contain duplicates")
    if maximum_history_draws is not None and maximum_history_draws <= 0:
        raise ReplayPredictionsCliError("maximum history draws must be positive")
    if minimum_history_draws is not None and minimum_history_draws <= 0:
        raise ReplayPredictionsCliError("minimum history draws must be positive")
    if (
        maximum_history_draws is not None
        and minimum_history_draws is not None
        and minimum_history_draws > maximum_history_draws
    ):
        raise ReplayPredictionsCliError("minimum history draws must not exceed maximum")


def _validate_strategies(catalog: StrategyCatalog, strategy_ids: tuple[str, ...]) -> None:
    for strategy_id in strategy_ids:
        try:
            descriptor = catalog.get(strategy_id)
        except UnknownStrategyError as exc:
            raise ReplayPredictionsCliError(f"unknown strategy ID: {strategy_id}") from exc
        if not descriptor.executable or LotteryType.BIG_LOTTO not in descriptor.lottery_types:
            raise ReplayPredictionsCliError(f"strategy is unavailable: {strategy_id}")


def _fail(message: str) -> NoReturn:
    typer.echo(f"replay-predictions error: {message}", err=True)
    raise typer.Exit(code=1)


__all__ = [
    "ReplayPredictionsCliError",
    "build_replay_predictions_cli_artifact",
    "replay_predictions_command",
]
