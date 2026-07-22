"""LottoLab CLI entry point."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab import __version__
from lottolab.application.local_runtime import (
    LocalRuntimeError,
    LocalRuntimePolicy,
    LocalRuntimeSafetyError,
    RuntimeStatus,
    RuntimeStatusKind,
)
from lottolab.application.use_cases.generate_bet import HistoryParseError, run_cli_generate_bet
from lottolab.infrastructure.local_runtime import LocalRuntimeSupervisor
from lottolab.interfaces.cli.replay_predictions import replay_predictions_command
from lottolab.strategies.catalog import production_catalog

app = typer.Typer(no_args_is_help=True, help="LottoLab — 樂透統計分析系統 CLI")
local_app = typer.Typer(no_args_is_help=True, help="Safely manage localhost-only services.")
app.add_typer(local_app, name="local")
app.command("replay-predictions")(replay_predictions_command)


@app.callback()
def root() -> None:
    """LottoLab CLI (keeps sub-command mode even with a single command)."""


@app.command()
def info() -> None:
    """Show runtime and catalog summary."""
    catalog = production_catalog()
    typer.echo(
        f"lottolab={__version__} python={platform.python_version()} strategies={len(catalog)}"
    )


@app.command("generate-bet")
def generate_bet_command(
    strategy_id: str,
    seed: Annotated[
        int,
        typer.Option(
            min=0,
            help=(
                "Caller-provided bookkeeping value echoed verbatim in the output; "
                "does not affect the generated numbers."
            ),
        ),
    ],
    history_file: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            help="Path to a JSON array of {draw, date, numbers} rows.",
        ),
    ],
) -> None:
    """Generate one deterministic BIG_LOTTO bet through the executable registry.

    The generated numbers are determined solely by ``strategy_id`` and
    history; ``seed`` is echoed in the JSON output as caller-provided
    bookkeeping metadata and never influences which numbers are produced.
    """
    try:
        history_json = history_file.read_text(encoding="utf-8")
        output, ok = run_cli_generate_bet(
            strategy_id=strategy_id, seed=seed, history_json=history_json
        )
    except (OSError, HistoryParseError) as exc:
        typer.echo(f"generate-bet input error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(output)
    if not ok:
        raise typer.Exit(code=1)


@local_app.command("start")
def local_start() -> None:
    """Start the backend and frontend on fixed localhost ports."""
    try:
        status = _local_supervisor().start()
    except LocalRuntimeError as exc:
        _local_failure(exc)
    if status.kind is not RuntimeStatusKind.RUNNING:
        _local_failure(
            LocalRuntimeSafetyError(
                f"start returned unexpected non-running state: {status.kind.value}"
            )
        )
    typer.echo(_format_status(status))
    typer.echo("backend=http://127.0.0.1:8000 frontend=http://127.0.0.1:5173")


@local_app.command("status")
def local_status() -> None:
    """Report controller state and verified process/listener ownership."""
    try:
        status = _local_supervisor().status()
    except LocalRuntimeError as exc:
        _local_failure(exc)
    typer.echo(_format_status(status))
    if status.kind in {RuntimeStatusKind.FOREIGN, RuntimeStatusKind.PARTIAL}:
        raise typer.Exit(code=1)


@local_app.command("smoke")
def local_smoke() -> None:
    """Verify health, frontend proxying, and the read-only Strategy Catalog."""
    try:
        report = _local_supervisor().smoke()
    except LocalRuntimeError as exc:
        _local_failure(exc)
    typer.echo(
        "smoke=pass ownership=verified listeners=localhost-only "
        f"strategies={','.join(report.strategy_ids)}"
    )


@local_app.command("stop")
def local_stop() -> None:
    """Stop only controller-owned processes and release both fixed ports."""
    try:
        status = _local_supervisor().stop()
    except LocalRuntimeError as exc:
        _local_failure(exc)
    typer.echo(_format_status(status))


def _local_supervisor() -> LocalRuntimeSupervisor:
    repository_root = Path(__file__).resolve().parents[4]
    return LocalRuntimeSupervisor(LocalRuntimePolicy.for_repository(repository_root))


def _local_failure(error: LocalRuntimeError) -> NoReturn:
    typer.echo(f"local runtime error: {error}", err=True)
    raise typer.Exit(code=1)


def _format_status(status: RuntimeStatus) -> str:
    ownership = "verified" if status.ownership_proven else "not-running"
    return (
        f"state={status.kind.value} ownership={ownership} "
        f"backend={status.backend} frontend={status.frontend} detail={status.detail}"
    )


def main() -> None:
    app()
