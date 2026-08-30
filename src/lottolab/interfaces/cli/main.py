"""LottoLab CLI entry point."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from lottolab import __version__
from lottolab.application.local_runtime import (
    ExpectedStrategy,
    LocalRuntimeError,
    LocalRuntimePolicy,
    LocalRuntimeSafetyError,
    RuntimeStatus,
    RuntimeStatusKind,
)
from lottolab.application.use_cases.generate_bet import (
    HistoryParseError,
    run_cli_generate_bet,
    run_cli_generate_portfolio,
)
from lottolab.infrastructure.local_runtime import LocalRuntimeSupervisor
from lottolab.interfaces.cli.biglotto_multi_ticket_backtest import (
    multi_ticket_backtest_command,
)
from lottolab.interfaces.cli.draw_data_integrity import draw_data_integrity_command
from lottolab.interfaces.cli.full_strategy_research import (
    export_full_strategy_research_catalog_command,
)
from lottolab.interfaces.cli.future_draw_identity import (
    supplement_future_draw_identity_command,
)
from lottolab.interfaces.cli.historical_import import historical_import_command
from lottolab.interfaces.cli.historical_replay_biglotto import (
    historical_replay_biglotto_command,
)
from lottolab.interfaces.cli.legacy_advanced_methods_native_batch_wave63 import (
    materialize_legacy_advanced_methods_native_wave63_batch_command,
)
from lottolab.interfaces.cli.legacy_checkpoint_native_batch_wave44 import (
    materialize_legacy_checkpoint_native_wave44_batch_command,
)
from lottolab.interfaces.cli.legacy_checkpoint_native_batch_wave55 import (
    materialize_legacy_checkpoint_native_wave55_batch_command,
)
from lottolab.interfaces.cli.legacy_diversified_native_batch_wave62 import (
    materialize_legacy_diversified_native_wave62_batch_command,
)
from lottolab.interfaces.cli.legacy_draw_import import legacy_draw_import_command
from lottolab.interfaces.cli.legacy_dual_seeded_native_batch_wave58 import (
    materialize_legacy_dual_seeded_native_wave58_batch_command,
)
from lottolab.interfaces.cli.legacy_evolution_native_batch_wave65 import (
    materialize_legacy_evolution_native_wave65_batch_command,
)
from lottolab.interfaces.cli.legacy_fft_native_batch_wave45 import (
    materialize_legacy_fft_native_wave45_batch_command,
)
from lottolab.interfaces.cli.legacy_five_bet_native_batch_wave61 import (
    materialize_legacy_five_bet_native_wave61_batch_command,
)
from lottolab.interfaces.cli.legacy_history_native_batch import (
    materialize_legacy_history_native_batch_command,
)
from lottolab.interfaces.cli.legacy_history_native_batch_wave2 import (
    materialize_legacy_history_native_wave2_batch_command,
)
from lottolab.interfaces.cli.legacy_history_native_batch_wave3 import (
    materialize_legacy_history_native_wave3_batch_command,
)
from lottolab.interfaces.cli.legacy_history_native_batch_wave5 import (
    materialize_legacy_history_native_wave5_batch_command,
)
from lottolab.interfaces.cli.legacy_hpsb_native_batch_wave57 import (
    materialize_legacy_hpsb_native_wave57_batch_command,
)
from lottolab.interfaces.cli.legacy_random_batch import (
    materialize_legacy_random_native_batch_command,
)
from lottolab.interfaces.cli.legacy_reference_import import (
    import_biglotto_legacy_reference_command,
)
from lottolab.interfaces.cli.legacy_seeded_benchmark_native_batch_wave60 import (
    materialize_legacy_seeded_benchmark_native_wave60_batch_command,
)
from lottolab.interfaces.cli.legacy_source_grid_native_batch_wave46 import (
    materialize_legacy_source_grid_native_wave46_batch_command,
)
from lottolab.interfaces.cli.legacy_source_grid_native_batch_wave47 import (
    materialize_legacy_source_grid_native_wave47_batch_command,
)
from lottolab.interfaces.cli.legacy_source_grid_native_batch_wave48 import (
    materialize_legacy_source_grid_native_wave48_batch_command,
)
from lottolab.interfaces.cli.legacy_source_grid_native_batch_wave49 import (
    materialize_legacy_source_grid_native_wave49_batch_command,
)
from lottolab.interfaces.cli.legacy_source_grid_native_batch_wave50 import (
    materialize_legacy_source_grid_native_wave50_batch_command,
)
from lottolab.interfaces.cli.legacy_source_grid_native_batch_wave51 import (
    materialize_legacy_source_grid_native_wave51_batch_command,
)
from lottolab.interfaces.cli.legacy_source_grid_native_batch_wave52 import (
    materialize_legacy_source_grid_native_wave52_batch_command,
)
from lottolab.interfaces.cli.legacy_source_grid_native_batch_wave53 import (
    materialize_legacy_source_grid_native_wave53_batch_command,
)
from lottolab.interfaces.cli.legacy_source_grid_native_batch_wave54 import (
    materialize_legacy_source_grid_native_wave54_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave6 import (
    materialize_legacy_source_native_wave6_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave7 import (
    materialize_legacy_source_native_wave7_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave8 import (
    materialize_legacy_source_native_wave8_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave9 import (
    materialize_legacy_source_native_wave9_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave11 import (
    materialize_legacy_source_native_wave11_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave12 import (
    materialize_legacy_source_native_wave12_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave14 import (
    materialize_legacy_source_native_wave14_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave15 import (
    materialize_legacy_source_native_wave15_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave16 import (
    materialize_legacy_source_native_wave16_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave17 import (
    materialize_legacy_source_native_wave17_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave20 import (
    materialize_legacy_source_native_wave20_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave21 import (
    materialize_legacy_source_native_wave21_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave22 import (
    materialize_legacy_source_native_wave22_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave23 import (
    materialize_legacy_source_native_wave23_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave24 import (
    materialize_legacy_source_native_wave24_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave25 import (
    materialize_legacy_source_native_wave25_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave26 import (
    materialize_legacy_source_native_wave26_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave27 import (
    materialize_legacy_source_native_wave27_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave28 import (
    materialize_legacy_source_native_wave28_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave29 import (
    materialize_legacy_source_native_wave29_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave30 import (
    materialize_legacy_source_native_wave30_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave31 import (
    materialize_legacy_source_native_wave31_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave32 import (
    materialize_legacy_source_native_wave32_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave33 import (
    materialize_legacy_source_native_wave33_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave34 import (
    materialize_legacy_source_native_wave34_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave40 import (
    materialize_legacy_source_native_wave40_batch_command,
)
from lottolab.interfaces.cli.legacy_source_native_batch_wave41 import (
    materialize_legacy_source_native_wave41_batch_command,
)
from lottolab.interfaces.cli.legacy_xgboost_native_batch_wave64 import (
    materialize_legacy_xgboost_native_wave64_batch_command,
)
from lottolab.interfaces.cli.ordered_candidate_materialization import (
    materialize_ordered_candidate_emissions_command,
)
from lottolab.interfaces.cli.p638_historical_forward import (
    forward_p638_historical_command,
)
from lottolab.interfaces.cli.pre_outcome_target import (
    register_pre_outcome_target_command,
)
from lottolab.interfaces.cli.replay_backed_batch import (
    materialize_exact_replay_batch_command,
)
from lottolab.interfaces.cli.replay_predictions import replay_predictions_command
from lottolab.interfaces.cli.research_backtest_runner import (
    run_biglotto_research_backtest_command,
)
from lottolab.interfaces.cli.research_store import research_store_command
from lottolab.interfaces.cli.t539_p638_schedule_certificate import (
    t539_p638_schedule_certificate_command,
)
from lottolab.interfaces.cli.taiwan_lottery_metadata_backfill import (
    taiwan_lottery_metadata_backfill_command,
)
from lottolab.strategies.catalog import production_catalog

app = typer.Typer(no_args_is_help=True, help="LottoLab — 樂透統計分析系統 CLI")
local_app = typer.Typer(no_args_is_help=True, help="Safely manage localhost-only services.")
app.add_typer(local_app, name="local")
app.command("import-historical-results")(historical_import_command)
app.command("forward-p638-historical")(forward_p638_historical_command)
app.command("replay-predictions")(replay_predictions_command)
app.command("register-pre-outcome-target")(register_pre_outcome_target_command)
app.command("supplement-future-draw-identity")(supplement_future_draw_identity_command)
app.command("t539-p638-schedule-certificate")(t539_p638_schedule_certificate_command)
app.command("research-store")(research_store_command)
app.command("run-biglotto-research-backtest")(run_biglotto_research_backtest_command)
app.command("import-biglotto-legacy-reference")(import_biglotto_legacy_reference_command)
app.command("inspect-draw-data-integrity")(draw_data_integrity_command)
app.command("import-legacy-draw-files")(legacy_draw_import_command)
app.command("backfill-taiwan-lottery-metadata")(taiwan_lottery_metadata_backfill_command)
app.command("materialize-ordered-candidate-emissions")(
    materialize_ordered_candidate_emissions_command
)
app.command("export-biglotto-strategy-universe")(export_full_strategy_research_catalog_command)
app.command("backtest-biglotto-portfolios")(multi_ticket_backtest_command)
app.command("historical-replay-biglotto")(historical_replay_biglotto_command)
app.command("materialize-biglotto-replay-batch")(materialize_exact_replay_batch_command)
app.command("materialize-biglotto-random-native-batch")(
    materialize_legacy_random_native_batch_command
)
app.command("materialize-biglotto-history-native-batch")(
    materialize_legacy_history_native_batch_command
)
app.command("materialize-biglotto-history-native-wave2-batch")(
    materialize_legacy_history_native_wave2_batch_command
)
app.command("materialize-biglotto-history-native-wave3-batch")(
    materialize_legacy_history_native_wave3_batch_command
)
app.command("materialize-biglotto-history-native-wave5-batch")(
    materialize_legacy_history_native_wave5_batch_command
)
app.command("materialize-biglotto-source-native-wave6-batch")(
    materialize_legacy_source_native_wave6_batch_command
)
app.command("materialize-biglotto-source-native-wave7-batch")(
    materialize_legacy_source_native_wave7_batch_command
)
app.command("materialize-biglotto-source-native-wave8-batch")(
    materialize_legacy_source_native_wave8_batch_command
)
app.command("materialize-biglotto-source-native-wave9-batch")(
    materialize_legacy_source_native_wave9_batch_command
)
app.command("materialize-biglotto-source-native-wave11-batch")(
    materialize_legacy_source_native_wave11_batch_command
)
app.command("materialize-biglotto-source-native-wave12-batch")(
    materialize_legacy_source_native_wave12_batch_command
)
app.command("materialize-biglotto-source-native-wave14-batch")(
    materialize_legacy_source_native_wave14_batch_command
)
app.command("materialize-biglotto-source-native-wave15-batch")(
    materialize_legacy_source_native_wave15_batch_command
)
app.command("materialize-biglotto-source-native-wave16-batch")(
    materialize_legacy_source_native_wave16_batch_command
)
app.command("materialize-biglotto-source-native-wave17-batch")(
    materialize_legacy_source_native_wave17_batch_command
)
app.command("materialize-biglotto-source-native-wave20-batch")(
    materialize_legacy_source_native_wave20_batch_command
)
app.command("materialize-biglotto-source-native-wave21-batch")(
    materialize_legacy_source_native_wave21_batch_command
)
app.command("materialize-biglotto-source-native-wave22-batch")(
    materialize_legacy_source_native_wave22_batch_command
)
app.command("materialize-biglotto-source-native-wave23-batch")(
    materialize_legacy_source_native_wave23_batch_command
)
app.command("materialize-biglotto-source-native-wave24-batch")(
    materialize_legacy_source_native_wave24_batch_command
)
app.command("materialize-biglotto-source-native-wave25-batch")(
    materialize_legacy_source_native_wave25_batch_command
)
app.command("materialize-biglotto-source-native-wave26-batch")(
    materialize_legacy_source_native_wave26_batch_command
)
app.command("materialize-biglotto-source-native-wave27-batch")(
    materialize_legacy_source_native_wave27_batch_command
)
app.command("materialize-biglotto-source-native-wave28-batch")(
    materialize_legacy_source_native_wave28_batch_command
)
app.command("materialize-biglotto-source-native-wave29-batch")(
    materialize_legacy_source_native_wave29_batch_command
)
app.command("materialize-biglotto-source-native-wave30-batch")(
    materialize_legacy_source_native_wave30_batch_command
)
app.command("materialize-biglotto-source-native-wave31-batch")(
    materialize_legacy_source_native_wave31_batch_command
)
app.command("materialize-biglotto-source-native-wave32-batch")(
    materialize_legacy_source_native_wave32_batch_command
)
app.command("materialize-biglotto-source-native-wave33-batch")(
    materialize_legacy_source_native_wave33_batch_command
)
app.command("materialize-biglotto-source-native-wave34-batch")(
    materialize_legacy_source_native_wave34_batch_command
)
app.command("materialize-biglotto-source-native-wave40-batch")(
    materialize_legacy_source_native_wave40_batch_command
)
app.command("materialize-biglotto-source-native-wave41-batch")(
    materialize_legacy_source_native_wave41_batch_command
)
app.command("materialize-biglotto-checkpoint-native-wave44-batch")(
    materialize_legacy_checkpoint_native_wave44_batch_command
)
app.command("materialize-biglotto-checkpoint-native-wave55-batch")(
    materialize_legacy_checkpoint_native_wave55_batch_command
)
app.command("materialize-biglotto-fft-native-wave45-batch")(
    materialize_legacy_fft_native_wave45_batch_command
)
app.command("materialize-biglotto-source-grid-native-wave46-batch")(
    materialize_legacy_source_grid_native_wave46_batch_command
)
app.command("materialize-biglotto-source-grid-native-wave47-batch")(
    materialize_legacy_source_grid_native_wave47_batch_command
)
app.command("materialize-biglotto-source-grid-native-wave48-batch")(
    materialize_legacy_source_grid_native_wave48_batch_command
)
app.command("materialize-biglotto-source-grid-native-wave49-batch")(
    materialize_legacy_source_grid_native_wave49_batch_command
)
app.command("materialize-biglotto-source-grid-native-wave50-batch")(
    materialize_legacy_source_grid_native_wave50_batch_command
)
app.command("materialize-biglotto-source-grid-native-wave51-batch")(
    materialize_legacy_source_grid_native_wave51_batch_command
)
app.command("materialize-biglotto-source-grid-native-wave52-batch")(
    materialize_legacy_source_grid_native_wave52_batch_command
)
app.command("materialize-biglotto-source-grid-native-wave53-batch")(
    materialize_legacy_source_grid_native_wave53_batch_command
)
app.command("materialize-biglotto-source-grid-native-wave54-batch")(
    materialize_legacy_source_grid_native_wave54_batch_command
)
app.command("materialize-biglotto-hpsb-native-wave57-batch")(
    materialize_legacy_hpsb_native_wave57_batch_command
)
app.command("materialize-biglotto-dual-seeded-native-wave58-batch")(
    materialize_legacy_dual_seeded_native_wave58_batch_command
)
app.command("materialize-biglotto-seeded-benchmark-native-wave60-batch")(
    materialize_legacy_seeded_benchmark_native_wave60_batch_command
)
app.command("materialize-biglotto-five-bet-native-wave61-batch")(
    materialize_legacy_five_bet_native_wave61_batch_command
)
app.command("materialize-biglotto-diversified-native-wave62-batch")(
    materialize_legacy_diversified_native_wave62_batch_command
)
app.command("materialize-biglotto-advanced-methods-native-wave63-batch")(
    materialize_legacy_advanced_methods_native_wave63_batch_command
)
app.command("materialize-biglotto-xgboost-native-wave64-batch")(
    materialize_legacy_xgboost_native_wave64_batch_command
)
app.command("materialize-biglotto-evolution-native-wave65-batch")(
    materialize_legacy_evolution_native_wave65_batch_command
)


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


@app.command("generate-bet-portfolio")
def generate_bet_portfolio_command(
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
    """Generate one strategy's complete native ticket portfolio (PORTFOLIO strategies only).

    Returns the full, ordered native ticket set — never truncated to one
    ticket. For SINGLE_TICKET strategy_ids, use ``generate-bet`` instead;
    this command fails closed (WRONG_RESPONSE_PATH) for those.
    """
    try:
        history_json = history_file.read_text(encoding="utf-8")
        output, ok = run_cli_generate_portfolio(
            strategy_id=strategy_id, seed=seed, history_json=history_json
        )
    except (OSError, HistoryParseError) as exc:
        typer.echo(f"generate-bet-portfolio input error: {exc}", err=True)
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
    expected_strategies = tuple(
        ExpectedStrategy(
            strategy_id=descriptor.strategy_id,
            lifecycle_status=descriptor.lifecycle_status.value,
            executable=descriptor.executable,
        )
        for descriptor in production_catalog()
    )
    return LocalRuntimeSupervisor(
        LocalRuntimePolicy.for_repository(repository_root),
        expected_strategies=expected_strategies,
    )


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
