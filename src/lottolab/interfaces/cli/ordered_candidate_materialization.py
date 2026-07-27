"""CLI composition for durable ordered-candidate materialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab.application.use_cases.generate_ordered_candidate_emission import (
    build_production_generate_ordered_candidate_emission,
)
from lottolab.application.use_cases.materialize_ordered_candidate_emissions import (
    MaterializeOrderedCandidateEmissions,
    MaterializeOrderedCandidateEmissionsInput,
    OrderedCandidateMaterializationInputError,
)
from lottolab.domain.draws import LotteryType
from lottolab.domain.ordered_candidate_materialization import (
    OrderedCandidateMaterializationSummary,
)
from lottolab.infrastructure.ordered_candidate_package_writer import (
    OrderedCandidatePackageWriter,
)
from lottolab.infrastructure.persistence.draw_schema import (
    resolve_local_data_paths,
)
from lottolab.infrastructure.persistence.ordered_candidate_materialization_reader import (
    SQLiteOrderedCandidateMaterializationReader,
)


class OrderedCandidateMaterializationCliError(RuntimeError):
    """A sanitized package-fatal CLI error."""


def build_ordered_candidate_materialization_cli_summary(
    *,
    lottery_type: str,
    dataset_id: str,
    dataset_version: str,
    source_snapshot_sha256: str,
    target_draws: tuple[str, ...],
    strategy_ids: tuple[str, ...],
    minimum_history_draws: int,
    maximum_history_draws: int,
    replicate: int,
    output_directory: Path,
) -> str:
    """Compose the production boundaries and return one compact sorted summary."""

    if lottery_type != LotteryType.BIG_LOTTO.value:
        raise OrderedCandidateMaterializationCliError(
            "lottery type must be BIG_LOTTO"
        )
    request = MaterializeOrderedCandidateEmissionsInput(
        lottery_type=LotteryType.BIG_LOTTO,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        expected_source_snapshot_sha256=source_snapshot_sha256,
        target_draws=target_draws,
        strategy_ids=strategy_ids,
        minimum_history_draws=minimum_history_draws,
        maximum_history_draws=maximum_history_draws,
        replicate=replicate,
        output_directory=output_directory,
    )
    try:
        if replicate != 1:
            raise OrderedCandidateMaterializationInputError(
                "replicate must be exactly 1"
            )
        paths = resolve_local_data_paths()
        result = MaterializeOrderedCandidateEmissions(
            reader_factory=lambda: SQLiteOrderedCandidateMaterializationReader(
                paths
            ),
            writer_factory=OrderedCandidatePackageWriter,
            generate_ordered_candidate_emission=(
                build_production_generate_ordered_candidate_emission()
            ),
        ).execute(request)
    except OrderedCandidateMaterializationInputError as exc:
        raise OrderedCandidateMaterializationCliError(str(exc)) from exc
    except Exception as exc:
        raise OrderedCandidateMaterializationCliError(
            "materialization failed safely"
        ) from exc
    return _summary_json(result)


def materialize_ordered_candidate_emissions_command(
    lottery_type: Annotated[str, typer.Option("--lottery-type")],
    dataset_id: Annotated[str, typer.Option("--dataset-id")],
    dataset_version: Annotated[str, typer.Option("--dataset-version")],
    source_snapshot_sha256: Annotated[
        str,
        typer.Option("--source-snapshot-sha256"),
    ],
    target_draw: Annotated[list[str], typer.Option("--target-draw")],
    strategy_id: Annotated[list[str], typer.Option("--strategy-id")],
    minimum_history_draws: Annotated[
        int,
        typer.Option("--minimum-history-draws"),
    ],
    maximum_history_draws: Annotated[
        int,
        typer.Option("--maximum-history-draws"),
    ],
    replicate: Annotated[int, typer.Option("--replicate")],
    output_directory: Annotated[Path, typer.Option("--output-directory")],
) -> None:
    """Seal caller-ordered BIG_LOTTO candidate emissions outside Git worktrees."""

    try:
        summary = build_ordered_candidate_materialization_cli_summary(
            lottery_type=lottery_type,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            source_snapshot_sha256=source_snapshot_sha256,
            target_draws=tuple(target_draw),
            strategy_ids=tuple(strategy_id),
            minimum_history_draws=minimum_history_draws,
            maximum_history_draws=maximum_history_draws,
            replicate=replicate,
            output_directory=output_directory,
        )
    except OrderedCandidateMaterializationCliError as exc:
        _fail(str(exc))
    except Exception:
        _fail("materialization failed safely")
    typer.echo(summary)


def _summary_json(result: OrderedCandidateMaterializationSummary) -> str:
    payload = {
        "attempt_count": result.attempt_count,
        "ok_attempt_count": result.ok_attempt_count,
        "output_directory": result.output_directory,
        "source_snapshot_sha256": result.source_snapshot_sha256,
        "status_counts": {
            status.value: count for status, count in result.status_counts
        },
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _fail(message: str) -> NoReturn:
    typer.echo(
        f"materialize-ordered-candidate-emissions error: {message}",
        err=True,
    )
    raise typer.Exit(code=1)


__all__ = [
    "OrderedCandidateMaterializationCliError",
    "build_ordered_candidate_materialization_cli_summary",
    "materialize_ordered_candidate_emissions_command",
]
