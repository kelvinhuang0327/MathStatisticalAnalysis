"""LottoLab CLI entry point."""

from __future__ import annotations

import platform

import typer

from lottolab import __version__
from lottolab.strategies.catalog import production_catalog

app = typer.Typer(no_args_is_help=True, help="LottoLab — 樂透統計分析系統 CLI")


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


def main() -> None:
    app()
